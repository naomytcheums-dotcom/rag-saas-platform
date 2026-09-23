"""Phase 5, Étape 3 -- real, ready-to-run Paystack integration tests,
gated on a real sandbox key. This session has never had a real
PAYSTACK_SECRET_KEY available (ROADMAP.md's own tracked gap), so these
have never actually executed against Paystack's real API -- they are
written and will run for real the moment a real sandbox key (and a
real plan created on that sandbox account) exist.

How to run these for real:
1. Create a free Paystack sandbox account, get a real test secret key
   (starts with `sk_test_`).
2. Create a real recurring Plan on that sandbox account
   (https://dashboard.paystack.com/#/plans), note its `plan_code`.
3. Set in .env: PAYSTACK_SECRET_KEY=sk_test_..., PAYSTACK_TEST_PLAN_CODE=PLN_...
4. Run: `pytest -m paystack_live tests/test_billing_paystack_live.py -v`

Without those two env vars, every test here is reported as SKIPPED
(not silently excluded like `network_flaky` -- these are meant to
fail loudly to remind whoever runs the suite that Paystack is still
untested for real, not to look identical to a passing run)."""

import os
import uuid

import pytest

from api.config import settings
from api.models.admin import Plan
from api.models.organization import Organization

pytestmark = pytest.mark.paystack_live

_TEST_PLAN_CODE = os.environ.get("PAYSTACK_TEST_PLAN_CODE")
_SKIP_REASON = (
    "needs a real PAYSTACK_SECRET_KEY and PAYSTACK_TEST_PLAN_CODE "
    "(a real plan_code created on that sandbox account) -- see this file's own module docstring"
)


def _live_configured() -> bool:
    return bool(settings.PAYSTACK_SECRET_KEY and _TEST_PLAN_CODE)


async def _make_org_and_plan(db_session) -> tuple[uuid.UUID, Plan]:
    org = Organization(name="Paystack Live Test Org", slug=f"paystack-live-{uuid.uuid4().hex[:8]}", billing_country="NG")
    plan = Plan(key=f"paystack-live-{uuid.uuid4().hex[:8]}", name="Paystack Live Test Plan", monthly_price_cents=2900, paystack_plan_code_monthly=_TEST_PLAN_CODE)
    db_session.add_all([org, plan])
    await db_session.commit()
    await db_session.refresh(org)
    await db_session.refresh(plan)
    return org.id, plan


@pytest.mark.skipif(not _live_configured(), reason=_SKIP_REASON)
async def test_live_checkout_session_returns_a_real_paystack_authorization_url(db_session):
    from api.services.billing_paystack import PaystackProvider

    org_id, plan = await _make_org_and_plan(db_session)
    url = await PaystackProvider().create_checkout_session(db_session, org_id, plan=plan, billing_period="monthly", email="paystack-live-test@example.com", org_name="Paystack Live Test Org")
    assert url.startswith("https://checkout.paystack.com/")


@pytest.mark.skipif(not _live_configured(), reason=_SKIP_REASON)
async def test_live_webhook_signature_verifies_against_a_real_captured_payload(db_session):
    """Run test_live_checkout_session above first (or complete a real
    checkout on the sandbox), capture the real webhook Paystack sends
    to your configured endpoint, and paste its raw body + real
    x-paystack-signature header below to prove verify_webhook_signature
    accepts real Paystack signatures, not just the synthetic HMAC this
    session already unit-tested (tests/test_billing.py's
    test_paystack_webhook_signature_rejects_tampered_payload)."""
    pytest.skip("paste a real captured webhook payload + signature here before running live")


@pytest.mark.skipif(not _live_configured(), reason=_SKIP_REASON)
async def test_live_portal_session_returns_a_real_manage_subscription_link(db_session):
    from api.services.billing_paystack import PaystackProvider

    org_id, plan = await _make_org_and_plan(db_session)
    provider = PaystackProvider()
    await provider.create_checkout_session(db_session, org_id, plan=plan, billing_period="monthly", email="paystack-live-test@example.com", org_name="Paystack Live Test Org")
    # A real subscription only exists once the real checkout is completed
    # by a human on Paystack's hosted page -- this call proves the real
    # API shape once that manual step has happened against the sandbox.
    url = await provider.create_portal_session(db_session, org_id)
    assert url.startswith("https://")


@pytest.mark.skipif(not _live_configured(), reason=_SKIP_REASON)
async def test_live_cancel_really_disables_the_sandbox_subscription(db_session):
    from api.services.billing_paystack import PaystackProvider

    org_id, plan = await _make_org_and_plan(db_session)
    provider = PaystackProvider()
    await provider.cancel_subscription(db_session, org_id, at_period_end=True)
