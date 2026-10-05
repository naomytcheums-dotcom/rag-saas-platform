"""Hardening Mission, §23 -- buying credit packs for real. The free direct
top-up used to be the ONLY way credits were ever added (and ignored whether a
payment provider was configured); closing it required a genuine purchase flow:
a one-off Stripe Checkout whose paid webhook grants the pack, idempotently.
The Stripe SDK is faked at its own boundary (no network); everything else --
DB rows, the webhook claim, the credit ledger, the HTTP routes -- is real."""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.billing import Credit, CreditTransaction
from api.models.organization import Organization
from api.security.credit_packs import get_credit_pack
from api.services import billing_stripe


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register_and_create_org(client, register_payload):
    token = (await client.post("/auth/register", json={"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True})).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Packs Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id


def _paid_session_event(org_id, pack_id="starter", *, event_id=None, payment_status="paid", amount=None, kind="credit_pack", session_id="cs_test_1") -> dict:
    pack = get_credit_pack(pack_id)
    return {
        "id": event_id or f"evt_{uuid.uuid4().hex}", "type": "checkout.session.completed",
        "data": {"object": {
            "id": session_id, "payment_status": payment_status, "amount_total": pack["price_cents"] if amount is None else amount,
            "metadata": {"organization_id": str(org_id), "kind": kind, "pack_id": pack_id},
        }},
    }


async def _org_with_credit(db_session, balance=100) -> uuid.UUID:
    org = Organization(name="Webhook Org", slug=f"wh-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    db_session.add(Credit(organization_id=org.id, balance=balance))
    await db_session.commit()
    return org.id


async def _balance(db_session, org_id) -> int:
    db_session.expire_all()
    return (await db_session.scalar(select(Credit).where(Credit.organization_id == org_id))).balance


# ------------------------------------------------------------- checkout creation (Stripe SDK faked)


async def test_checkout_session_is_a_one_off_payment_for_exactly_the_pack_with_server_set_metadata(monkeypatch, db_session):
    captured = {}

    class _Session:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return {"url": "https://checkout.stripe.test/s/abc"}

    class _Stripe:
        class Customer:
            @staticmethod
            def create(**kwargs):
                return {"id": "cus_123"}

        class checkout:  # noqa: N801 -- mirrors the SDK's attribute path
            Session = _Session

    monkeypatch.setattr(billing_stripe, "_client", lambda: _Stripe)
    org = Organization(name="Checkout Org", slug=f"co-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.commit()
    pack = get_credit_pack("pro")

    url = await billing_stripe.create_credit_pack_checkout_session(db_session, org.id, pack=pack, email="a@b.co", org_name="Checkout Org")

    assert url == "https://checkout.stripe.test/s/abc"
    assert captured["mode"] == "payment"
    item = captured["line_items"][0]
    assert item["quantity"] == 1 and item["price_data"]["unit_amount"] == pack["price_cents"] and item["price_data"]["currency"] == settings.CREDIT_PACK_CURRENCY
    assert captured["metadata"] == {"organization_id": str(org.id), "kind": "credit_pack", "pack_id": "pro"}


# ------------------------------------------------------------------ webhook grants (real DB)


async def test_a_paid_checkout_grants_exactly_the_packs_credits_and_records_the_ledger_entry(db_session):
    org_id = await _org_with_credit(db_session, balance=100)

    applied = await billing_stripe.handle_stripe_webhook(db_session, _paid_session_event(org_id, "starter"))
    await db_session.commit()

    assert applied is True
    assert await _balance(db_session, org_id) == 100 + get_credit_pack("starter")["credits"]
    entry = await db_session.scalar(select(CreditTransaction).where(CreditTransaction.organization_id == org_id).order_by(CreditTransaction.created_at.desc()))
    assert entry.amount == get_credit_pack("starter")["credits"] and "cs_test_1" in entry.reason


async def test_a_redelivered_event_never_grants_twice(db_session):
    org_id = await _org_with_credit(db_session, balance=0)
    event = _paid_session_event(org_id, "starter", event_id="evt_same")

    first = await billing_stripe.handle_stripe_webhook(db_session, event)
    await db_session.commit()
    second = await billing_stripe.handle_stripe_webhook(db_session, event)
    await db_session.commit()

    assert (first, second) == (True, False)
    assert await _balance(db_session, org_id) == get_credit_pack("starter")["credits"]


@pytest.mark.parametrize("label, overrides", [
    ("unpaid session", {"payment_status": "unpaid"}),
    ("amount that is not the pack's price", {"amount": 1}),
    ("unknown pack", {"pack_id": "does-not-exist"}),
])
async def test_anything_that_does_not_match_a_real_paid_pack_grants_nothing(db_session, label, overrides):
    org_id = await _org_with_credit(db_session, balance=50)
    pack_id = overrides.pop("pack_id", "starter")
    event = _paid_session_event(org_id, "starter", **overrides)
    event["data"]["object"]["metadata"]["pack_id"] = pack_id

    await billing_stripe.handle_stripe_webhook(db_session, event)
    await db_session.commit()

    assert await _balance(db_session, org_id) == 50, label


async def test_a_checkout_that_is_not_a_credit_pack_and_a_bad_organization_id_grant_nothing(db_session):
    org_id = await _org_with_credit(db_session, balance=50)
    other_kind = _paid_session_event(org_id, "starter", kind="something_else")
    bad_org = _paid_session_event(org_id, "starter")
    bad_org["data"]["object"]["metadata"]["organization_id"] = "not-a-uuid"

    await billing_stripe.handle_stripe_webhook(db_session, other_kind)
    await billing_stripe.handle_stripe_webhook(db_session, bad_org)
    await db_session.commit()

    assert await _balance(db_session, org_id) == 50


# ----------------------------------------------------------------------------- the route


async def test_the_credit_checkout_route_returns_the_providers_hosted_url(monkeypatch, client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_configured")
    create = AsyncMock(return_value="https://checkout.stripe.test/s/xyz")
    monkeypatch.setattr(billing_stripe, "create_credit_pack_checkout_session", create)

    response = await client.post(f"/organizations/{org_id}/billing/credits/checkout", json={"pack_id": "pro"}, headers=_auth_header(token))

    assert response.status_code == 200 and response.json() == {"url": "https://checkout.stripe.test/s/xyz"}
    assert create.await_args.kwargs["pack"]["id"] == "pro"


async def test_the_credit_checkout_route_is_honest_without_a_provider_and_for_an_unknown_pack(monkeypatch, client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", None)
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", None)

    unconfigured = await client.post(f"/organizations/{org_id}/billing/credits/checkout", json={"pack_id": "pro"}, headers=_auth_header(token))
    unknown = await client.post(f"/organizations/{org_id}/billing/credits/checkout", json={"pack_id": "nope"}, headers=_auth_header(token))

    assert unconfigured.status_code == 501 and unknown.status_code == 404


async def test_a_provider_without_credit_pack_support_says_so_instead_of_faking_it(monkeypatch, client, register_payload):
    from api.services.billing_providers.base import BillingProvider

    token, org_id = await _register_and_create_org(client, register_payload)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_configured")

    async def _unsupported(self, *args, **kwargs):
        return await BillingProvider.create_credit_pack_checkout(self, *args, **kwargs)

    monkeypatch.setattr(billing_stripe.StripeProvider, "create_credit_pack_checkout", _unsupported)
    response = await client.post(f"/organizations/{org_id}/billing/credits/checkout", json={"pack_id": "pro"}, headers=_auth_header(token))

    assert response.status_code == 501 and "does not support credit pack purchases" in response.json()["detail"]
