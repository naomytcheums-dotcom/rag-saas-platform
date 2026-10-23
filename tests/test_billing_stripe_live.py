"""Phase 5, Étape 24 -- real, ready-to-run Stripe integration tests,
gated on a real test-mode key. Symmetric with
tests/test_billing_paystack_live.py: without a real STRIPE_SECRET_KEY
and STRIPE_TEST_PRICE_ID, every test here is reported as SKIPPED (not
silently excluded like `network_flaky`).

How to run these for real:
1. Create a free Stripe account (test mode is enabled by default).
2. Get a real test secret key (starts with `sk_test_`) from
   https://dashboard.stripe.com/test/apikeys.
3. Create a real recurring Price on that test account
   (https://dashboard.stripe.com/test/products), note its `price_id`
   (starts with `price_`).
4. Set in .env: STRIPE_SECRET_KEY=sk_test_..., STRIPE_TEST_PRICE_ID=price_...
5. Run: `pytest -m stripe_live tests/test_billing_stripe_live.py -v`, or `python scripts/run_live_tests.py --provider stripe --env-file <file outside the repo>`.
6. Optional, for the webhook test: STRIPE_TEST_WEBHOOK_PAYLOAD_FILE (raw body of a captured test event), STRIPE_TEST_WEBHOOK_SIGNATURE
   (its Stripe-Signature header) and STRIPE_WEBHOOK_SECRET (the matching whsec_...).

Without those two env vars, every test here is reported as SKIPPED."""

import hashlib
import hmac
import os
import time
import uuid
from pathlib import Path

import pytest

from api.config import settings
from api.models.admin import Plan
from api.models.organization import Organization

pytestmark = pytest.mark.stripe_live

_TEST_PRICE_ID = os.environ.get("STRIPE_TEST_PRICE_ID")
_SKIP_REASON = (
    "needs a real STRIPE_SECRET_KEY and STRIPE_TEST_PRICE_ID "
    "(a real price_id created on that test account) -- see this file's own module docstring"
)


def _live_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY and _TEST_PRICE_ID)


_WEBHOOK_PAYLOAD_FILE = os.environ.get("STRIPE_TEST_WEBHOOK_PAYLOAD_FILE")
_WEBHOOK_SIGNATURE = os.environ.get("STRIPE_TEST_WEBHOOK_SIGNATURE")
_WEBHOOK_SKIP_REASON = (
    "needs a real STRIPE_SECRET_KEY plus a real captured webhook: STRIPE_TEST_WEBHOOK_PAYLOAD_FILE, STRIPE_TEST_WEBHOOK_SIGNATURE and "
    "STRIPE_WEBHOOK_SECRET -- see this file's own module docstring"
)


def _webhook_configured() -> bool:
    return bool(_live_configured() and _WEBHOOK_PAYLOAD_FILE and _WEBHOOK_SIGNATURE and settings.STRIPE_WEBHOOK_SECRET)

async def _make_org_and_plan(db_session) -> tuple[uuid.UUID, Plan]:
    org = Organization(name="Stripe Live Test Org", slug=f"stripe-live-{uuid.uuid4().hex[:8]}", billing_country="US")
    plan = Plan(key=f"stripe-live-{uuid.uuid4().hex[:8]}", name="Stripe Live Test Plan", monthly_price_cents=2900, stripe_price_id_monthly=_TEST_PRICE_ID)
    db_session.add_all([org, plan])
    await db_session.commit()
    await db_session.refresh(org)
    await db_session.refresh(plan)
    return org.id, plan


@pytest.mark.skipif(not _live_configured(), reason=_SKIP_REASON)
async def test_live_checkout_session_returns_a_real_stripe_authorization_url(db_session):
    from api.services.billing_stripe import StripeProvider

    org_id, plan = await _make_org_and_plan(db_session)
    url = await StripeProvider().create_checkout_session(db_session, org_id, plan=plan, billing_period="monthly", email="stripe-live-test@example.com", org_name="Stripe Live Test Org")
    assert url.startswith("https://checkout.stripe.com/")


def _verify_captured_webhook(payload: bytes, signature_header: str):
    """Runs the application's own `verify_webhook_signature` on a captured event.

    Stripe refuses an event signed more than 5 minutes ago, and a captured event is older than that by definition: the clock is pinned to the
    timestamp inside the signature header while the call runs, so what is checked is the SIGNATURE, not the age of the capture."""
    from api.services.billing_stripe import verify_webhook_signature

    signed_at = next(int(part[2:]) for part in signature_header.split(",") if part.startswith("t="))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(time, "time", lambda: float(signed_at))
        return verify_webhook_signature(payload, signature_header)


@pytest.mark.skipif(not _webhook_configured(), reason=_WEBHOOK_SKIP_REASON)
async def test_live_webhook_signature_verifies_against_a_real_captured_payload(db_session):
    """Proves `verify_webhook_signature` accepts a REAL Stripe signature, not only the synthetic HMAC of tests/test_billing.py.

    Capture a real event from the test account (Stripe CLI `stripe listen`, or the dashboard's event detail), save its raw body to a file
    OUTSIDE the repository and note its `Stripe-Signature` header, then run scripts/run_live_tests.py with STRIPE_TEST_WEBHOOK_PAYLOAD_FILE,
    STRIPE_TEST_WEBHOOK_SIGNATURE and STRIPE_WEBHOOK_SECRET (the `whsec_...` of that endpoint or CLI session) in the env file."""
    import stripe

    payload = Path(_WEBHOOK_PAYLOAD_FILE).read_bytes()
    event = _verify_captured_webhook(payload, _WEBHOOK_SIGNATURE)
    assert str(event["id"]).startswith("evt_") and event["type"]
    with pytest.raises(stripe.SignatureVerificationError):
        _verify_captured_webhook(payload + b" ", _WEBHOOK_SIGNATURE)


async def test_the_captured_webhook_helper_works_on_a_synthetic_event_NOT_a_live_test(monkeypatch):
    """Not a live test and not evidence about Stripe: it proves the helper above is correct (an old timestamp is accepted, a tampered body is
    refused) with an event signed by a FAKE secret, so that the live test is already exercised the day real data is supplied."""
    import stripe

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_synthetic_not_real")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_synthetic_not_real")
    payload = b'{"id": "evt_synthetic", "object": "event", "type": "invoice.paid", "data": {"object": {}}}'
    signed_at = 1_700_000_000  # years old: Stripe's 5-minute tolerance would refuse it without the pinned clock
    digest = hmac.new(b"whsec_synthetic_not_real", f"{signed_at}.".encode() + payload, hashlib.sha256).hexdigest()
    header = f"t={signed_at},v1={digest}"

    assert _verify_captured_webhook(payload, header)["id"] == "evt_synthetic"
    with pytest.raises(stripe.SignatureVerificationError):
        _verify_captured_webhook(payload + b" ", header)
    with pytest.raises(stripe.SignatureVerificationError):
        _verify_captured_webhook(payload, f"t={signed_at},v1={'0' * 64}")

@pytest.mark.skipif(not _live_configured(), reason=_SKIP_REASON)
async def test_live_portal_session_returns_a_real_manage_subscription_link(db_session):
    from api.services.billing_stripe import StripeProvider

    org_id, plan = await _make_org_and_plan(db_session)
    provider = StripeProvider()
    await provider.create_checkout_session(db_session, org_id, plan=plan, billing_period="monthly", email="stripe-live-test@example.com", org_name="Stripe Live Test Org")
    # A real subscription only exists once the real checkout is completed
    # by a human on Stripe's hosted page.
    url = await provider.create_portal_session(db_session, org_id)
    assert url.startswith("https://billing.stripe.com/")


@pytest.mark.skipif(not _live_configured(), reason=_SKIP_REASON)
async def test_live_cancel_really_disables_the_test_subscription(db_session):
    from api.services.billing_stripe import StripeProvider

    org_id, plan = await _make_org_and_plan(db_session)
    provider = StripeProvider()
    await provider.cancel_subscription(db_session, org_id, at_period_end=True)
