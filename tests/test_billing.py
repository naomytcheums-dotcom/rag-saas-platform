"""Partie 12 -- billing: plans catalog, subscription lifecycle, credits,
usage limits, invoices (incl. real PDF generation), and Stripe's honest
501-when-unconfigured behavior."""

import uuid

import pytest


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register_and_create_org(client, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Billing Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id


async def test_plans_catalog_is_public_and_seeds_a_real_free_plan(client):
    response = await client.get("/billing/plans")
    assert response.status_code == 200
    assert any(p["key"] == "free" and p["monthly_price_cents"] == 0 for p in response.json())


async def test_get_plan_404_for_unknown_id(client):
    response = await client.get(f"/billing/plans/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_new_organization_gets_a_real_free_subscription(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.get(f"/organizations/{org_id}/billing/subscription", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert response.json()["billing_period"] == "monthly"


async def test_non_owner_member_cannot_subscribe(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User

    token, org_id = await _register_and_create_org(client, register_payload)
    plans = (await client.get("/billing/plans")).json()
    plan_id = plans[0]["id"]

    # Downgrade the caller's own role to member to prove this is enforced,
    # not just "never tested".
    from api.models.organization import OrganizationMember, OrganizationRole

    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    membership = await db_session.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == uuid.UUID(org_id), OrganizationMember.user_id == user.id))
    membership.role = OrganizationRole.member
    await db_session.commit()

    response = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": plan_id}, headers=_auth_header(token))
    assert response.status_code == 403


async def test_owner_can_subscribe_upgrade_cancel_reactivate(client, db_session, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)

    # /admin/plans requires platform-admin, which this test's user is not --
    # create the plan directly via the model instead of that endpoint.
    from api.models.admin import Plan

    plan = Plan(key="pro-billing-test", name="Pro Test", monthly_price_cents=2900, yearly_price_cents=29000)
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)

    subscribe = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": str(plan.id), "billing_period": "monthly"}, headers=_auth_header(token))
    assert subscribe.status_code == 200
    assert subscribe.json()["plan_id"] == str(plan.id)

    cancel = await client.post(f"/organizations/{org_id}/billing/cancel", json={"reason": "test"}, headers=_auth_header(token))
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "canceled"

    reactivate = await client.post(f"/organizations/{org_id}/billing/reactivate", headers=_auth_header(token))
    assert reactivate.status_code == 200
    assert reactivate.json()["status"] == "active"


async def test_credits_default_grant_and_purchase_pack(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)

    credits = await client.get(f"/organizations/{org_id}/billing/credits", headers=_auth_header(token))
    assert credits.status_code == 200
    initial_balance = credits.json()["balance"]
    assert initial_balance > 0  # real signup grant, not zero/fake

    purchase = await client.post(f"/organizations/{org_id}/billing/credits/purchase", json={"pack_id": "starter"}, headers=_auth_header(token))
    assert purchase.status_code == 200
    assert purchase.json()["balance"] == initial_balance + 10_000

    transactions = await client.get(f"/organizations/{org_id}/billing/credits/transactions", headers=_auth_header(token))
    assert transactions.status_code == 200
    assert len(transactions.json()) == 2  # grant + purchase


async def test_purchase_unknown_pack_404s(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.post(f"/organizations/{org_id}/billing/credits/purchase", json={"pack_id": "does-not-exist"}, headers=_auth_header(token))
    assert response.status_code == 404


async def test_usage_endpoints_return_real_zero_without_fabricating_data(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.get(f"/organizations/{org_id}/billing/usage", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["total_by_metric"] == {}


async def test_check_limits_enforced_against_real_plan_max(db_session, register_payload, client):
    from sqlalchemy import select

    from api.models.admin import Plan, Subscription
    from api.security.usage import record_usage
    from api.services.billing_usage import check_limits

    token, org_id = await _register_and_create_org(client, register_payload)
    org_uuid = uuid.UUID(org_id)
    await client.get(f"/organizations/{org_id}/billing/subscription", headers=_auth_header(token))  # ensures a real subscription row exists

    plan = Plan(key="capped-plan", name="Capped", monthly_price_cents=0, max_documents=2)
    db_session.add(plan)
    await db_session.flush()
    sub = await db_session.scalar(select(Subscription).where(Subscription.organization_id == org_uuid))
    sub.plan_id = plan.id
    await db_session.commit()

    assert await check_limits(db_session, org_uuid, "documents_processed", 1) is True
    await record_usage(db_session, org_uuid, "documents_processed", 2)
    await db_session.commit()
    assert await check_limits(db_session, org_uuid, "documents_processed", 1) is False


async def test_create_invoice_list_and_pdf(client, db_session, register_payload):
    from api.services.billing_invoices import create_invoice, generate_invoice_pdf, PDFUnavailableError

    token, org_id = await _register_and_create_org(client, register_payload)
    org_uuid = uuid.UUID(org_id)

    invoice = await create_invoice(db_session, org_uuid, lines=[{"description": "Pro plan", "quantity": 1, "unit_price_cents": 2900}])
    await db_session.commit()
    assert invoice.total_cents == 2900 + round(2900 * 0.20)

    listing = await client.get(f"/organizations/{org_id}/billing/invoices", headers=_auth_header(token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    try:
        pdf_bytes = await generate_invoice_pdf(db_session, org_uuid, invoice.id)
        assert pdf_bytes[:4] == b"%PDF"
    except PDFUnavailableError:
        pass  # honest, environment-dependent -- see requirements-api.txt's own comment


async def test_stripe_checkout_honestly_501s_without_configured_keys(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.post(f"/organizations/{org_id}/billing/stripe/create-checkout-session", json={"price_id": "price_fake"}, headers=_auth_header(token))
    assert response.status_code == 501


async def test_stripe_webhook_501s_without_configured_secret(client):
    response = await client.post("/billing/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=fake"})
    assert response.status_code == 501


# -- Phase 5, Étape 2: Paystack + provider-generic billing --------------------

async def test_paystack_webhook_501s_without_configured_secret(client):
    response = await client.post("/billing/paystack/webhook", content=b"{}", headers={"x-paystack-signature": "fake"})
    assert response.status_code == 501


async def test_unified_checkout_501s_without_any_configured_provider(client, db_session, register_payload):
    from api.models.admin import Plan

    token, org_id = await _register_and_create_org(client, register_payload)
    plan = Plan(key="pro-unified-test", name="Pro Unified", monthly_price_cents=2900, yearly_price_cents=29000)
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)

    response = await client.post(f"/organizations/{org_id}/billing/checkout", json={"plan_id": str(plan.id)}, headers=_auth_header(token))
    assert response.status_code == 501


async def test_unified_checkout_requires_owner(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.organization import OrganizationMember, OrganizationRole
    from api.models.user import User

    token, org_id = await _register_and_create_org(client, register_payload)
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    membership = await db_session.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == uuid.UUID(org_id), OrganizationMember.user_id == user.id))
    membership.role = OrganizationRole.member
    await db_session.commit()

    response = await client.post(f"/organizations/{org_id}/billing/checkout", json={"plan_id": str(uuid.uuid4())}, headers=_auth_header(token))
    assert response.status_code == 403


async def test_billing_provider_endpoint_reports_none_when_unconfigured(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.get(f"/organizations/{org_id}/billing/provider", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json() == {"provider": "none", "configured": False}


async def test_billing_country_roundtrip_and_validation(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)

    get_response = await client.get(f"/organizations/{org_id}/billing/country", headers=_auth_header(token))
    assert get_response.status_code == 200
    assert get_response.json() == {"billing_country": None}

    set_response = await client.patch(f"/organizations/{org_id}/billing/country", json={"billing_country": "ng"}, headers=_auth_header(token))
    assert set_response.status_code == 200
    assert set_response.json() == {"billing_country": "NG"}

    invalid = await client.patch(f"/organizations/{org_id}/billing/country", json={"billing_country": "NGA"}, headers=_auth_header(token))
    assert invalid.status_code == 422


async def test_billing_country_update_requires_owner(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.organization import OrganizationMember, OrganizationRole
    from api.models.user import User

    token, org_id = await _register_and_create_org(client, register_payload)
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    membership = await db_session.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == uuid.UUID(org_id), OrganizationMember.user_id == user.id))
    membership.role = OrganizationRole.member
    await db_session.commit()

    response = await client.patch(f"/organizations/{org_id}/billing/country", json={"billing_country": "NG"}, headers=_auth_header(token))
    assert response.status_code == 403


async def test_registry_resolves_paystack_for_paystack_country_when_configured(db_session, monkeypatch):
    from api.config import settings
    from api.models.organization import Organization
    from api.services.billing_providers.registry import resolve_provider_for_organization

    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_fake")

    org = Organization(name="Lagos Org", slug="lagos-org-registry-test", billing_country="NG")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    provider = await resolve_provider_for_organization(db_session, org.id)
    assert provider.name == "paystack"


async def test_registry_falls_back_to_stripe_for_non_paystack_country(db_session, monkeypatch):
    from api.config import settings
    from api.models.organization import Organization
    from api.services.billing_providers.registry import resolve_provider_for_organization

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_fake")

    org = Organization(name="Paris Org", slug="paris-org-registry-test", billing_country="FR")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    provider = await resolve_provider_for_organization(db_session, org.id)
    assert provider.name == "stripe"


async def test_registry_raises_not_configured_when_resolved_provider_has_no_key(db_session):
    from api.models.organization import Organization
    from api.services.billing_providers.base import ProviderNotConfiguredError
    from api.services.billing_providers.registry import resolve_provider_for_organization

    org = Organization(name="Accra Org", slug="accra-org-registry-test", billing_country="GH")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    with pytest.raises(ProviderNotConfiguredError):
        await resolve_provider_for_organization(db_session, org.id)


def test_get_provider_rejects_unknown_provider_name():
    from api.services.billing_providers.registry import get_provider

    with pytest.raises(ValueError):
        get_provider("unknown-provider")


def test_paystack_webhook_signature_rejects_tampered_payload(monkeypatch):
    import hashlib
    import hmac

    from api.config import settings
    from api.services.billing_paystack import verify_webhook_signature

    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_fake")
    payload = b'{"event": "charge.success", "data": {"id": 1}}'
    real_signature = hmac.new(b"sk_test_fake", payload, hashlib.sha512).hexdigest()

    event = verify_webhook_signature(payload, real_signature)
    assert event["event"] == "charge.success"

    with pytest.raises(ValueError):
        verify_webhook_signature(payload, "0" * 128)


async def test_paystack_webhook_is_idempotent_on_repeated_event(db_session):
    from api.services.billing_paystack import handle_paystack_webhook

    event = {"event": "charge.success", "data": {"id": 999999, "metadata": {}}}
    first = await handle_paystack_webhook(db_session, event)
    await db_session.commit()
    second = await handle_paystack_webhook(db_session, event)
    assert first is True
    assert second is False


async def test_paystack_webhook_reconciles_subscription_status_via_customer_code(db_session, register_payload, client):
    from api.models.admin import Plan, Subscription, SubscriptionStatus
    from api.models.billing import PaymentCustomer, PaymentProvider
    from api.services.billing_paystack import handle_paystack_webhook

    token, org_id = await _register_and_create_org(client, register_payload)
    org_uuid = uuid.UUID(org_id)

    plan = Plan(key="pro-paystack-webhook-test", name="Pro Paystack", monthly_price_cents=2900, yearly_price_cents=29000)
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)

    sub = Subscription(organization_id=org_uuid, plan_id=plan.id, status=SubscriptionStatus.active)
    customer = PaymentCustomer(organization_id=org_uuid, provider=PaymentProvider.paystack, external_customer_id="CUS_test123")
    db_session.add_all([sub, customer])
    await db_session.commit()

    event = {"event": "subscription.disable", "data": {"subscription_code": "SUB_test123", "customer": {"customer_code": "CUS_test123"}}}
    applied = await handle_paystack_webhook(db_session, event)
    await db_session.commit()
    assert applied is True

    await db_session.refresh(sub)
    assert sub.status == SubscriptionStatus.canceled
