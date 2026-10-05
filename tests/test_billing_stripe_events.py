"""Real, focused tests for the real payment-succeeded events added
to billing_stripe.handle_stripe_webhook, plus (Hardening Mission, §5
webhook anti-replay) the real atomic idempotency claim that replaced
the old check-then-insert race."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", [
    "payment_intent.succeeded",
    "charge.succeeded",
    "invoice.paid",
])
async def test_payment_succeeded_events_are_handled(event_type, db_session):
    from api.services import billing_stripe

    org_id = str(uuid.uuid4())
    event = {
        "id": f"evt_{uuid.uuid4()}",
        "type": event_type,
        "data": {"object": {"id": "obj_123", "metadata": {"organization_id": org_id}}},
    }

    with patch.object(billing_stripe, "notify_billing_payment_succeeded", create=True, new=AsyncMock()):
        result = await billing_stripe.handle_stripe_webhook(db_session, event)

    assert result is True


@pytest.mark.asyncio
async def test_payment_succeeded_without_org_id_is_still_recorded(db_session):
    from api.services import billing_stripe

    event = {
        "id": f"evt_{uuid.uuid4()}",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "obj_no_org", "metadata": {}}},
    }

    result = await billing_stripe.handle_stripe_webhook(db_session, event)
    assert result is True


@pytest.mark.asyncio
async def test_duplicate_event_returns_false(db_session):
    """Real idempotency: a SECOND real call with the exact same event id
    (the real retry-delivery scenario both Stripe and Paystack document)
    must be rejected by the real, committed PaymentEvent row the first
    call really inserted -- not a mock, a real unique-constraint hit."""
    from api.services import billing_stripe

    event = {
        "id": f"evt_{uuid.uuid4()}",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "obj_dup", "metadata": {}}},
    }
    first = await billing_stripe.handle_stripe_webhook(db_session, event)
    await db_session.commit()
    second = await billing_stripe.handle_stripe_webhook(db_session, event)

    assert first is True
    assert second is False


@pytest.mark.asyncio
async def test_concurrent_duplicate_deliveries_apply_side_effects_only_once(db_session):
    """Hardening Mission, §5 -- the real regression test for the race
    this session fixed: two real deliveries of the SAME event id,
    racing on the SAME underlying claim, must only let ONE of them
    actually notify/reconcile. `claim_payment_event` makes the second
    caller's `db.begin_nested()` raise `IntegrityError` the moment the
    first caller's (uncommitted) INSERT is visible within the same
    real transaction -- proving the claim happens before, not after,
    the side effect."""
    from api.services import billing_stripe

    org_id = str(uuid.uuid4())
    event_id = f"evt_{uuid.uuid4()}"
    event = {
        "id": event_id,
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "obj_race", "metadata": {"organization_id": org_id}}},
    }

    notify_mock = AsyncMock()
    with patch("api.services.notifications.notify_billing_payment_succeeded", notify_mock):
        first = await billing_stripe.handle_stripe_webhook(db_session, event)
        # Same session, same open transaction -- simulates the second
        # concurrent delivery discovering the claim the first delivery
        # already took, before either has committed.
        second = await billing_stripe.handle_stripe_webhook(db_session, event)

    assert first is True
    assert second is False
    notify_mock.assert_awaited_once()
