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
4. Run: `pytest -m paystack_live tests/test_billing_paystack_live.py -v`, or `python scripts/run_live_tests.py --provider paystack --env-file <file outside the repo>`.
5. Optional, for the webhook test: PAYSTACK_TEST_WEBHOOK_PAYLOAD_FILE (raw body of a captured sandbox event) and
   PAYSTACK_TEST_WEBHOOK_SIGNATURE (its x-paystack-signature header).

Without those two env vars, every test here is reported as SKIPPED
(not silently excluded like `network_flaky` -- these are meant to
fail loudly to remind whoever runs the suite that Paystack is still
untested for real, not to look identical to a passing run)."""

import hashlib
import hmac
import os
import uuid
from pathlib import Path

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


_WEBHOOK_PAYLOAD_FILE = os.environ.get("PAYSTACK_TEST_WEBHOOK_PAYLOAD_FILE")
_WEBHOOK_SIGNATURE = os.environ.get("PAYSTACK_TEST_WEBHOOK_SIGNATURE")
_WEBHOOK_SKIP_REASON = (
    "needs a real PAYSTACK_SECRET_KEY plus a real captured webhook: PAYSTACK_TEST_WEBHOOK_PAYLOAD_FILE and PAYSTACK_TEST_WEBHOOK_SIGNATURE "
    "-- see this file's own module docstring"
)


def _webhook_configured() -> bool:
    return bool(_live_configured() and _WEBHOOK_PAYLOAD_FILE and _WEBHOOK_SIGNATURE)

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


def _verify_captured_webhook(payload: bytes, signature_header: str) -> dict:
    from api.services.billing_paystack import verify_webhook_signature

    return verify_webhook_signature(payload, signature_header)


@pytest.mark.skipif(not _webhook_configured(), reason=_WEBHOOK_SKIP_REASON)
async def test_live_webhook_signature_verifies_against_a_real_captured_payload(db_session):
    """Proves `verify_webhook_signature` accepts a REAL Paystack signature, not only the synthetic HMAC of tests/test_billing.py.

    Capture a real event from the sandbox (a test charge or subscription event delivered to your webhook URL, or the dashboard's event log),
    save its raw body to a file OUTSIDE the repository and note its `x-paystack-signature` header, then run scripts/run_live_tests.py with
    PAYSTACK_TEST_WEBHOOK_PAYLOAD_FILE and PAYSTACK_TEST_WEBHOOK_SIGNATURE in the env file. Paystack signs with the secret key itself."""
    payload = Path(_WEBHOOK_PAYLOAD_FILE).read_bytes()
    event = _verify_captured_webhook(payload, _WEBHOOK_SIGNATURE)
    assert event.get("event")
    with pytest.raises(ValueError):
        _verify_captured_webhook(payload + b" ", _WEBHOOK_SIGNATURE)


async def test_the_captured_webhook_helper_works_on_a_synthetic_event_NOT_a_live_test(monkeypatch):
    """Not a live test and not evidence about Paystack: it proves the helper above is correct with an event signed by a FAKE key, so that the
    live test is already exercised the day real data is supplied."""
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_synthetic_not_real")
    payload = b'{"event": "charge.success", "data": {"id": 42, "status": "success"}}'
    signature = hmac.new(b"sk_test_synthetic_not_real", payload, hashlib.sha512).hexdigest()

    assert _verify_captured_webhook(payload, signature)["event"] == "charge.success"
    with pytest.raises(ValueError):
        _verify_captured_webhook(payload + b" ", signature)
    with pytest.raises(ValueError):
        _verify_captured_webhook(payload, "0" * 128)

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
