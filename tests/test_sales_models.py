"""Partie 16 (bis) -- self-hosted licensing, hybrid support/SLA,
white-label reseller/sub-client, and real SaaS plan-limit enforcement.

Partie 18 adds: self-service partner registration, the persisted
partner-commission ledger (create/list/pay + the batched Celery-task
logic), license expiry re-validation, and the SaaS usage-limit-warning
sweep."""

import datetime as dt
import uuid


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _make_superadmin(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.superadmin
    await db_session.commit()
    return token, user


async def _register_and_create_org(client, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Sales Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id


# -- Self-hosted licensing ----------------------------------------------------

async def test_generate_validate_activate_license(client, db_session, register_payload):
    admin_token, _ = await _make_superadmin(client, db_session, register_payload)
    generated = await client.post("/license/generate", json={"plan_key": "pro", "max_activations": 1}, headers=_auth_header(admin_token))
    assert generated.status_code == 201
    key = generated.json()["key"]

    validated = await client.post("/license/validate", json={"key": key})
    assert validated.status_code == 200
    assert validated.json()["valid"] is True

    org_id = (await client.post("/organizations", json={"name": "Licensed Org"}, headers=_auth_header(admin_token))).json()["id"]
    activated = await client.post(f"/organizations/{org_id}/license/activate", json={"key": key}, headers=_auth_header(admin_token))
    assert activated.status_code == 200
    assert activated.json()["activation_count"] == 1


async def test_license_activation_limit_enforced(client, db_session, register_payload):
    admin_token, _ = await _make_superadmin(client, db_session, register_payload)
    generated = await client.post("/license/generate", json={"plan_key": "starter", "max_activations": 1}, headers=_auth_header(admin_token))
    key = generated.json()["key"]

    org1 = (await client.post("/organizations", json={"name": "Org One"}, headers=_auth_header(admin_token))).json()["id"]
    await client.post(f"/organizations/{org1}/license/activate", json={"key": key}, headers=_auth_header(admin_token))

    org2 = (await client.post("/organizations", json={"name": "Org Two"}, headers=_auth_header(admin_token))).json()["id"]
    second = await client.post(f"/organizations/{org2}/license/activate", json={"key": key}, headers=_auth_header(admin_token))
    assert second.status_code == 400


async def test_validate_unknown_license_key(client):
    response = await client.post("/license/validate", json={"key": "NOT-A-REAL-KEY"})
    assert response.status_code == 200
    assert response.json()["valid"] is False


# -- Hybrid: support tickets + SLA --------------------------------------------

async def test_create_ticket_and_check_sla(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(f"/organizations/{org_id}/support/tickets", json={"subject": "Help", "description": "Something broke", "priority": "critical"}, headers=_auth_header(token))
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    sla = await client.get(f"/organizations/{org_id}/support/tickets/{ticket_id}/sla", headers=_auth_header(token))
    assert sla.status_code == 200
    assert sla.json()["target_hours"] == 1  # critical priority's real SLA target
    assert sla.json()["responded_at"] is None


async def test_respond_to_ticket(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(f"/organizations/{org_id}/support/tickets", json={"subject": "Help", "description": "x"}, headers=_auth_header(token))
    ticket_id = created.json()["id"]

    response = await client.post(f"/organizations/{org_id}/support/tickets/{ticket_id}/respond", json={"body": "We're looking into it"}, headers=_auth_header(token))
    assert response.status_code == 201

    listing = await client.get(f"/organizations/{org_id}/support/tickets", headers=_auth_header(token))
    assert listing.json()[0]["status"] == "open"  # a non-staff response doesn't advance status


# -- White-label: reseller / sub-clients --------------------------------------

async def test_reseller_and_sub_client_commission(client, db_session, register_payload):
    admin_token, _ = await _make_superadmin(client, db_session, register_payload)
    reseller_org = (await client.post("/organizations", json={"name": "Reseller Co"}, headers=_auth_header(admin_token))).json()["id"]
    reseller = await client.post("/reseller/create", json={"organization_id": reseller_org, "commission_percent": 30}, headers=_auth_header(admin_token))
    assert reseller.status_code == 201
    reseller_id = reseller.json()["id"]

    client_org_id = (await client.post("/organizations", json={"name": "Sub Client Co"}, headers=_auth_header(admin_token))).json()["id"]
    added = await client.post(f"/reseller/{reseller_id}/clients", json={"organization_id": client_org_id}, headers=_auth_header(admin_token))
    assert added.status_code == 201

    from sqlalchemy import select

    from api.models.admin import Plan, Subscription

    plan = Plan(key="reseller-test-plan", name="Test", monthly_price_cents=10000)
    db_session.add(plan)
    await db_session.flush()
    await client.get(f"/organizations/{client_org_id}/billing/subscription", headers=_auth_header(admin_token))
    sub = await db_session.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(client_org_id)))
    sub.plan_id = plan.id
    await db_session.commit()

    commission = await client.get(f"/reseller/{reseller_id}/commission", headers=_auth_header(admin_token))
    assert commission.status_code == 200
    assert commission.json()["sub_client_mrr_cents"] == 10000
    assert commission.json()["commission_cents"] == 3000


# -- SaaS: real plan-limit enforcement ----------------------------------------

async def test_document_upload_blocked_when_plan_limit_reached(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.admin import Plan, Subscription

    token, org_id = await _register_and_create_org(client, register_payload)
    await client.get(f"/organizations/{org_id}/billing/subscription", headers=_auth_header(token))

    plan = Plan(key="zero-docs-plan", name="Zero Docs", monthly_price_cents=0, max_documents=0)
    db_session.add(plan)
    await db_session.flush()
    sub = await db_session.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(org_id)))
    sub.plan_id = plan.id
    await db_session.commit()

    response = await client.post(
        f"/organizations/{org_id}/documents", headers=_auth_header(token),
        files={"file": ("test.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 402


# -- Partner program (Partie 18): self-service signup + commission ledger ----

async def test_register_partner_creates_account_org_and_reseller(client):
    response = await client.post("/partners/register", json={
        "organization_name": "Acme Resellers", "email": "partner1@example.com", "password": "correct horse battery staple 42",
    })
    assert response.status_code == 201
    body = response.json()
    assert body["reseller"]["commission_percent"] == 20  # settings.PARTNER_DEFAULT_COMMISSION
    assert body["reseller"]["is_active"] is True


async def test_registered_partner_can_reach_their_own_dashboard(client):
    await client.post("/partners/register", json={
        "organization_name": "Beta Resellers", "email": "partner2@example.com", "password": "correct horse battery staple 42",
    })
    login = await client.post("/auth/login", json={"email": "partner2@example.com", "password": "correct horse battery staple 42"})
    token = login.json()["access_token"]

    me = await client.get("/partners/me", headers=_auth_header(token))
    assert me.status_code == 200
    assert me.json()["commission_percent"] == 20

    clients = await client.get("/partners/me/clients", headers=_auth_header(token))
    assert clients.status_code == 200
    assert clients.json() == []

    commissions = await client.get("/partners/me/commissions", headers=_auth_header(token))
    assert commissions.status_code == 200
    assert commissions.json() == []


async def test_non_partner_gets_404_from_partners_me(client, register_payload):
    token, _org_id = await _register_and_create_org(client, register_payload)
    response = await client.get("/partners/me", headers=_auth_header(token))
    assert response.status_code == 404


async def test_registering_the_same_partner_email_twice_is_rejected(client):
    payload = {"organization_name": "Gamma Resellers", "email": "partner3@example.com", "password": "correct horse battery staple 42"}
    first = await client.post("/partners/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/partners/register", json=payload)
    assert second.status_code == 409


async def test_admin_creates_lists_and_pays_a_partner_commission(client, db_session, register_payload):
    from api.models.sales import Reseller

    admin_token, _ = await _make_superadmin(client, db_session, register_payload)
    reseller_org = (await client.post("/organizations", json={"name": "Commission Reseller Co"}, headers=_auth_header(admin_token))).json()["id"]
    reseller_resp = await client.post("/reseller/create", json={"organization_id": reseller_org, "commission_percent": 25}, headers=_auth_header(admin_token))
    reseller_id = reseller_resp.json()["id"]

    from api.services.sales import create_partner_commission

    reseller_row = await db_session.get(Reseller, uuid.UUID(reseller_id))
    commission = await create_partner_commission(
        db_session, reseller_row.id, period_start=dt.date(2026, 8, 1), period_end=dt.date(2026, 8, 31), amount_cents=5000,
    )
    await db_session.commit()

    listed = await client.get(f"/partners/{reseller_id}/commissions", headers=_auth_header(admin_token))
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["status"] == "pending"

    paid = await client.post(f"/partners/commissions/{commission.id}/pay", headers=_auth_header(admin_token))
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"
    assert paid.json()["paid_at"] is not None

    already_paid = await client.post(f"/partners/commissions/{commission.id}/pay", headers=_auth_header(admin_token))
    assert already_paid.status_code == 400


async def test_calculate_and_record_commissions_is_idempotent_per_period(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.admin import Plan, Subscription
    from api.services.sales import add_sub_client, calculate_and_record_commissions_for_period, create_reseller

    admin_token, _ = await _make_superadmin(client, db_session, register_payload)
    reseller_org_id = (await client.post("/organizations", json={"name": "Idempotent Reseller"}, headers=_auth_header(admin_token))).json()["id"]
    reseller = await create_reseller(db_session, uuid.UUID(reseller_org_id), commission_percent=20)
    await db_session.commit()

    client_org_id = (await client.post("/organizations", json={"name": "Idempotent Sub Client"}, headers=_auth_header(admin_token))).json()["id"]
    await add_sub_client(db_session, reseller.id, uuid.UUID(client_org_id))
    plan = Plan(key="idempotent-plan", name="Idempotent", monthly_price_cents=20000)
    db_session.add(plan)
    await db_session.flush()
    await client.get(f"/organizations/{client_org_id}/billing/subscription", headers=_auth_header(admin_token))
    sub = await db_session.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(client_org_id)))
    sub.plan_id = plan.id
    await db_session.commit()

    period_start, period_end = dt.date(2026, 7, 1), dt.date(2026, 7, 31)
    first_run = await calculate_and_record_commissions_for_period(db_session, period_start=period_start, period_end=period_end)
    await db_session.commit()
    assert first_run == 1  # one real row created for this reseller/period

    second_run = await calculate_and_record_commissions_for_period(db_session, period_start=period_start, period_end=period_end)
    await db_session.commit()
    assert second_run == 0  # same period -- real idempotency, no duplicate row

    from api.services.sales import list_partner_commissions
    rows = await list_partner_commissions(db_session, reseller.id)
    assert len(rows) == 1
    assert rows[0].amount_cents == 4000  # 20% of 20000


async def test_pay_eligible_commissions_respects_minimum_payout(client, db_session, register_payload):
    from api.models.sales import PartnerCommissionStatus
    from api.services.sales import create_partner_commission, create_reseller, pay_eligible_commissions

    admin_token, _ = await _make_superadmin(client, db_session, register_payload)
    below_org_id = (await client.post("/organizations", json={"name": "Below Threshold Reseller"}, headers=_auth_header(admin_token))).json()["id"]
    below_reseller = await create_reseller(db_session, uuid.UUID(below_org_id))
    above_org_id = (await client.post("/organizations", json={"name": "Above Threshold Reseller"}, headers=_auth_header(admin_token))).json()["id"]
    above_reseller = await create_reseller(db_session, uuid.UUID(above_org_id))
    await db_session.commit()

    below_commission = await create_partner_commission(db_session, below_reseller.id, period_start=dt.date(2026, 6, 1), period_end=dt.date(2026, 6, 30), amount_cents=500)
    above_commission = await create_partner_commission(db_session, above_reseller.id, period_start=dt.date(2026, 6, 1), period_end=dt.date(2026, 6, 30), amount_cents=15000)
    await db_session.commit()

    result = await pay_eligible_commissions(db_session)
    await db_session.commit()
    assert result == {"resellers_paid": 1, "commissions_paid": 1}

    await db_session.refresh(below_commission)
    await db_session.refresh(above_commission)
    assert below_commission.status == PartnerCommissionStatus.pending  # under settings.PARTNER_MIN_PAYOUT_CENTS -- stays real and unpaid
    assert above_commission.status == PartnerCommissionStatus.paid


# -- Self-hosted licensing (Partie 18): periodic re-validation ---------------

async def test_expire_overdue_licenses_flips_status_for_real(db_session):
    from api.models.sales import License, LicenseStatus, generate_license_key
    from api.services.sales import expire_overdue_licenses

    overdue = License(
        key=generate_license_key(), plan_key="pro", max_activations=1,
        expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
    )
    still_valid = License(
        key=generate_license_key(), plan_key="pro", max_activations=1,
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30),
    )
    db_session.add_all([overdue, still_valid])
    await db_session.commit()

    expired_count = await expire_overdue_licenses(db_session)
    await db_session.commit()
    assert expired_count == 1

    await db_session.refresh(overdue)
    await db_session.refresh(still_valid)
    assert overdue.status == LicenseStatus.expired
    assert still_valid.status == LicenseStatus.active
