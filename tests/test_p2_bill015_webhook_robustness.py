"""BILL-015: webhook robustness. Providers are not contacted: events are synthetic, signature verification is monkeypatched where needed."""

import uuid

from sqlalchemy import select

from api.models.billing import Credit
from api.security.credit_packs import get_credit_pack
from api.services import billing_paystack, billing_stripe
from test_billing_credit_packs import _paid_session_event


async def test_paystack_events_without_any_object_id_do_not_block_each_other(db_session):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    event_a = {"event": "charge.success", "data": {"metadata": {"organization_id": str(org_a)}}}
    event_b = {"event": "charge.success", "data": {"metadata": {"organization_id": str(org_b)}}}

    first = await billing_paystack.handle_paystack_webhook(db_session, event_a)
    second = await billing_paystack.handle_paystack_webhook(db_session, event_b)  # another organization: not a duplicate
    again = await billing_paystack.handle_paystack_webhook(db_session, event_a)  # the very same payload: a duplicate

    assert (first, second, again) == (True, True, False)


async def test_a_stripe_event_without_an_object_is_ignored_not_a_500(db_session):
    assert await billing_stripe.handle_stripe_webhook(db_session, {"id": "evt_no_object", "type": "customer.subscription.updated", "data": {}}) is False
    assert await billing_stripe.handle_stripe_webhook(db_session, {"id": "evt_no_data", "type": "customer.subscription.updated"}) is False
    assert await billing_stripe.handle_stripe_webhook(db_session, {"type": "invoice.paid", "data": {"object": {}}}) is False  # no event id


async def test_a_paid_pack_for_an_organization_that_does_not_exist_grants_nothing(db_session):
    ghost = uuid.uuid4()

    await billing_stripe.handle_stripe_webhook(db_session, _paid_session_event(ghost, "starter", session_id="cs_ghost"))
    await db_session.commit()

    assert await db_session.scalar(select(Credit).where(Credit.organization_id == ghost)) is None
    assert get_credit_pack("starter") is not None


async def test_a_missing_stripe_sdk_is_not_reported_as_an_invalid_signature(client, monkeypatch):
    def _no_sdk(payload, signature):
        raise ImportError("No module named 'stripe'")

    monkeypatch.setattr(billing_stripe, "verify_webhook_signature", _no_sdk)

    response = await client.post("/billing/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})

    assert response.status_code == 503 and "Invalid" not in response.text


async def test_a_bad_signature_is_still_a_400(client, monkeypatch):
    def _bad(payload, signature):
        raise ValueError("signature mismatch")

    monkeypatch.setattr(billing_stripe, "verify_webhook_signature", _bad)

    response = await client.post("/billing/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})

    assert response.status_code == 400 and response.json()["detail"] == "Invalid Stripe signature"
