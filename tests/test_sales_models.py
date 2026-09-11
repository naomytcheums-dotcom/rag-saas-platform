"""Partie 16 (bis) -- self-hosted licensing, hybrid support/SLA,
white-label reseller/sub-client, and real SaaS plan-limit enforcement."""

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
