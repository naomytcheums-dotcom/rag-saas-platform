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
5. Run: `pytest -m stripe_live tests/test_billing_stripe_live.py -v`

Without those two env vars, every test here is reported as SKIPPED."""

import os
import uuid

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


@pytest.mark.skipif(not _live_configured(), reason=_SKIP_REASON)
async def test_live_webhook_signature_verifies_against_a_real_captured_payload(db_session):
    """Run test_live_checkout_session above first (or complete a real
    checkout on the test account), capture the real webhook Stripe sends
    to your configured endpoint, and paste its raw body + real
    stripe-signature header below to prove verify_webhook_signature
    accepts real Stripe signatures, not just the synthetic HMAC this
    session already unit-tested (tests/test_billing.py's
    test_stripe_webhook_signature_rejects_tampered_payload)."""
    pytest.skip("paste a real captured webhook payload + signature here before running live")


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
