"""P0 billing (BILL-001 / BILL-002 / UX-001): an organization must not be able to give itself a paid plan or mark an
invoice paid without a payment. No payment provider, LLM or e-mail is ever contacted: the provider is a local fake."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.admin import Plan, Subscription
from api.models.billing import Invoice, InvoiceStatus
from api.models.user import User, UserRole
from api.services.billing_invoices import create_invoice
from api.services.billing_providers.base import ProviderNotConfiguredError


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _org(client, register_payload) -> tuple[str, uuid.UUID]:
    with patch("api.routers.auth.create_and_send_email_otp", new=AsyncMock()):
        token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Billing P0 Org"}, headers=_auth(token))).json()["id"]
    return token, uuid.UUID(org_id)


async def _plans(client) -> dict[str, dict]:
    return {p["key"]: p for p in (await client.get("/billing/plans")).json()}


async def _current_plan_id(db_session, org_id: uuid.UUID) -> uuid.UUID:
    db_session.expire_all()
    return (await db_session.scalar(select(Subscription).where(Subscription.organization_id == org_id))).plan_id


async def _put_org_on_plan(client, db_session, token: str, org_id: uuid.UUID, plan_id: str, billing_period: str = "monthly") -> None:
    """Simulates what a confirmed payment would have done (the provider webhook), directly in the database."""
    await client.get(f"/organizations/{org_id}/billing/subscription", headers=_auth(token))
    sub = await db_session.scalar(select(Subscription).where(Subscription.organization_id == org_id))
    sub.plan_id = uuid.UUID(plan_id)
    sub.billing_period = billing_period
    await db_session.commit()


class _FakeProvider:
    name = "fake"

    def __init__(self):
        self.calls = []

    async def create_checkout_session(self, db, org_id, *, plan, billing_period, email, org_name):
        self.calls.append((org_id, plan.key, billing_period))
        return "https://checkout.example/session/xyz"


# -- BILL-001 / UX-001: no free paid plan ------------------------------------------------------------------------------

@pytest.mark.parametrize("route", ["subscribe", "upgrade", "downgrade"])
@pytest.mark.parametrize("period", ["monthly", "yearly"])
async def test_owner_cannot_give_itself_enterprise_for_free(client, db_session, register_payload, route, period):
    token, org_id = await _org(client, register_payload)
    plans = await _plans(client)
    await client.get(f"/organizations/{org_id}/billing/subscription", headers=_auth(token))
    before = await _current_plan_id(db_session, org_id)

    response = await client.post(
        f"/organizations/{org_id}/billing/{route}", json={"plan_id": plans["enterprise"]["id"], "billing_period": period}, headers=_auth(token),
    )

    assert response.status_code in (402, 403), response.text
    assert "checkout" in response.json()["detail"].lower()
    assert await _current_plan_id(db_session, org_id) == before == uuid.UUID(plans["free"]["id"])


async def test_every_paid_plan_is_refused_not_only_enterprise(client, db_session, register_payload):
    token, org_id = await _org(client, register_payload)
    plans = await _plans(client)

    for key in ("starter", "pro", "enterprise"):
        response = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": plans[key]["id"]}, headers=_auth(token))
        assert response.status_code == 402, key
    assert await _current_plan_id(db_session, org_id) == uuid.UUID(plans["free"]["id"])


async def test_paid_plan_refused_even_when_the_plan_only_has_a_yearly_price(client, db_session, register_payload):
    token, org_id = await _org(client, register_payload)
    plan = Plan(key="yearly-only-p0", name="Yearly only", monthly_price_cents=0, yearly_price_cents=120000)
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    plan_id = str(plan.id)
    await client.get(f"/organizations/{org_id}/billing/subscription", headers=_auth(token))
    before = await _current_plan_id(db_session, org_id)

    response = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": plan_id, "billing_period": "yearly"}, headers=_auth(token))

    assert response.status_code == 402
    assert await _current_plan_id(db_session, org_id) == before


async def test_unknown_plan_is_a_404_and_changes_nothing(client, db_session, register_payload):
    token, org_id = await _org(client, register_payload)
    await client.get(f"/organizations/{org_id}/billing/subscription", headers=_auth(token))
    before = await _current_plan_id(db_session, org_id)

    response = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": str(uuid.uuid4())}, headers=_auth(token))

    assert response.status_code == 404
    assert await _current_plan_id(db_session, org_id) == before


async def test_switching_to_the_free_plan_still_works(client, db_session, register_payload):
    token, org_id = await _org(client, register_payload)
    plans = await _plans(client)
    await _put_org_on_plan(client, db_session, token, org_id, plans["pro"]["id"])

    response = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": plans["free"]["id"], "billing_period": "monthly"}, headers=_auth(token))

    assert response.status_code == 200, response.text
    assert response.json()["plan_id"] == plans["free"]["id"]
    assert await _current_plan_id(db_session, org_id) == uuid.UUID(plans["free"]["id"])


async def test_free_to_free_subscribe_still_works(client, register_payload):
    token, org_id = await _org(client, register_payload)
    plans = await _plans(client)

    response = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": plans["free"]["id"]}, headers=_auth(token))

    assert response.status_code == 200
    assert response.json()["plan_id"] == plans["free"]["id"]


async def test_downgrade_to_a_strictly_cheaper_paid_plan_is_allowed_but_not_the_other_way(client, db_session, register_payload):
    token, org_id = await _org(client, register_payload)
    plans = await _plans(client)
    await _put_org_on_plan(client, db_session, token, org_id, plans["enterprise"]["id"])

    down = await client.post(f"/organizations/{org_id}/billing/downgrade", json={"plan_id": plans["starter"]["id"]}, headers=_auth(token))
    assert down.status_code == 200, down.text
    assert await _current_plan_id(db_session, org_id) == uuid.UUID(plans["starter"]["id"])

    up = await client.post(f"/organizations/{org_id}/billing/upgrade", json={"plan_id": plans["enterprise"]["id"]}, headers=_auth(token))
    assert up.status_code == 402
    assert await _current_plan_id(db_session, org_id) == uuid.UUID(plans["starter"]["id"])


async def test_reselecting_the_current_paid_plan_is_a_harmless_noop_but_switching_period_needs_checkout(client, db_session, register_payload):
    token, org_id = await _org(client, register_payload)
    plans = await _plans(client)
    await _put_org_on_plan(client, db_session, token, org_id, plans["pro"]["id"], "monthly")

    same = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": plans["pro"]["id"], "billing_period": "monthly"}, headers=_auth(token))
    assert same.status_code == 200

    other_period = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": plans["pro"]["id"], "billing_period": "yearly"}, headers=_auth(token))
    assert other_period.status_code == 402


async def test_explicit_dev_opt_in_restores_self_service_paid_plans(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_ALLOW_SELF_SERVICE_PAID_PLANS", True)
    token, org_id = await _org(client, register_payload)
    plans = await _plans(client)

    response = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": plans["enterprise"]["id"]}, headers=_auth(token))

    assert response.status_code == 200
    assert await _current_plan_id(db_session, org_id) == uuid.UUID(plans["enterprise"]["id"])


def test_self_service_paid_plans_is_off_by_default():
    assert type(settings).model_fields["BILLING_ALLOW_SELF_SERVICE_PAID_PLANS"].default is False


# -- the nominal paid path still works: checkout (never a direct plan write) ---------------------------------------------

async def test_nominal_checkout_returns_the_provider_url_and_does_not_touch_the_plan(client, db_session, register_payload, monkeypatch):
    provider = _FakeProvider()
    monkeypatch.setattr("api.routers.billing.resolve_provider_for_organization", AsyncMock(return_value=provider))
    token, org_id = await _org(client, register_payload)
    plans = await _plans(client)
    await client.get(f"/organizations/{org_id}/billing/subscription", headers=_auth(token))
    before = await _current_plan_id(db_session, org_id)

    response = await client.post(f"/organizations/{org_id}/billing/checkout", json={"plan_id": plans["pro"]["id"], "billing_period": "yearly"}, headers=_auth(token))

    assert response.status_code == 200, response.text
    assert response.json() == {"url": "https://checkout.example/session/xyz"}
    assert provider.calls == [(org_id, "pro", "yearly")]
    assert await _current_plan_id(db_session, org_id) == before  # only a verified provider webhook may change it


async def test_checkout_without_a_configured_provider_is_a_clear_501(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.routers.billing.resolve_provider_for_organization", AsyncMock(side_effect=ProviderNotConfiguredError("No payment provider is configured")))
    token, org_id = await _org(client, register_payload)
    plans = await _plans(client)
    await client.get(f"/organizations/{org_id}/billing/subscription", headers=_auth(token))
    before = await _current_plan_id(db_session, org_id)

    response = await client.post(f"/organizations/{org_id}/billing/checkout", json={"plan_id": plans["enterprise"]["id"]}, headers=_auth(token))

    assert response.status_code == 501
    assert await _current_plan_id(db_session, org_id) == before


async def test_a_non_owner_member_still_gets_403_on_subscribe(client, db_session, register_payload):
    from api.models.organization import OrganizationMember, OrganizationRole

    token, org_id = await _org(client, register_payload)
    plans = await _plans(client)
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    membership = await db_session.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == user.id))
    membership.role = OrganizationRole.member
    await db_session.commit()

    response = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": plans["free"]["id"]}, headers=_auth(token))

    assert response.status_code == 403


# -- BILL-002: an organization cannot mark its own invoice paid --------------------------------------------------------

async def _pending_invoice(db_session, org_id: uuid.UUID) -> uuid.UUID:
    invoice = await create_invoice(db_session, org_id, lines=[{"description": "Pro plan", "quantity": 1, "unit_price_cents": 19900}])
    invoice.status = InvoiceStatus.pending  # the helper's name was always "pending"; create_invoice leaves a draft, which can no longer be marked paid
    await db_session.commit()
    return invoice.id


async def _invoice_status(db_session, invoice_id: uuid.UUID):
    db_session.expire_all()
    invoice = await db_session.get(Invoice, invoice_id)
    return invoice.status, invoice.paid_at


async def test_owner_cannot_mark_its_own_invoice_paid(client, db_session, register_payload):
    token, org_id = await _org(client, register_payload)
    invoice_id = await _pending_invoice(db_session, org_id)
    status_before, _ = await _invoice_status(db_session, invoice_id)

    response = await client.post(f"/organizations/{org_id}/billing/invoices/{invoice_id}/pay", headers=_auth(token))

    assert response.status_code == 403
    status_after, paid_at = await _invoice_status(db_session, invoice_id)
    assert status_after == status_before != InvoiceStatus.paid
    assert paid_at is None


async def test_a_platform_admin_can_still_reconcile_an_invoice(client, db_session, register_payload):
    token, org_id = await _org(client, register_payload)
    invoice_id = await _pending_invoice(db_session, org_id)
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.superadmin  # SADM-005 / BILL-002: reconciliation is a superadmin act (a plain admin is refused, see test_p1_bill002_invoice_state_machine.py)
    await db_session.commit()

    response = await client.post(f"/organizations/{org_id}/billing/invoices/{invoice_id}/pay", json={"reference": "WIRE-2026-0001"}, headers=_auth(token))

    assert response.status_code == 200, response.text
    status_after, paid_at = await _invoice_status(db_session, invoice_id)
    assert status_after == InvoiceStatus.paid and paid_at is not None


async def test_dev_opt_in_lets_an_owner_mark_an_invoice_paid(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_ALLOW_SELF_SERVICE_PAID_PLANS", True)
    token, org_id = await _org(client, register_payload)
    invoice_id = await _pending_invoice(db_session, org_id)

    response = await client.post(f"/organizations/{org_id}/billing/invoices/{invoice_id}/pay", headers=_auth(token))

    assert response.status_code == 200
    assert (await _invoice_status(db_session, invoice_id))[0] == InvoiceStatus.paid
