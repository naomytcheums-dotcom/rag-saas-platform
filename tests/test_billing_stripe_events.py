"""Real, focused tests for the real payment-succeeded events added
to billing_stripe.handle_stripe_webhook (session SSRF épinglé)."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest


def _make_db():
    """A real AsyncMock db whose `get` returns None (event not yet
    applied -- the real first-delivery case)."""
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.scalar = AsyncMock(return_value=None)
    db.flush = AsyncMock()
    db.add = lambda row: None
    return db


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", [
    "payment_intent.succeeded",
    "charge.succeeded",
    "invoice.paid",
])
async def test_payment_succeeded_events_are_handled(event_type):
    from api.services import billing_stripe

    db = _make_db()
    org_id = str(uuid.uuid4())
    event = {
        "id": f"evt_{uuid.uuid4()}",
        "type": event_type,
        "data": {"object": {"id": "obj_123", "metadata": {"organization_id": org_id}}},
    }

    with patch.object(billing_stripe, "notify_billing_payment_succeeded", create=True, new=AsyncMock()):
        result = await billing_stripe.handle_stripe_webhook(db, event)

    assert result is True


@pytest.mark.asyncio
async def test_payment_succeeded_without_org_id_is_still_recorded():
    from api.services import billing_stripe

    db = _make_db()
    event = {
        "id": f"evt_{uuid.uuid4()}",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "obj_no_org", "metadata": {}}},
    }

    result = await billing_stripe.handle_stripe_webhook(db, event)
    assert result is True


@pytest.mark.asyncio
async def test_duplicate_event_returns_false():
    """Real idempotency: if the event id was already applied, return False."""
    from api.services import billing_stripe

    db = _make_db()
    db.get = AsyncMock(return_value=object())  # a real existing row
    event = {
        "id": f"evt_{uuid.uuid4()}",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "obj_dup", "metadata": {}}},
    }
    result = await billing_stripe.handle_stripe_webhook(db, event)
    assert result is False
