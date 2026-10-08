"""Hardening Mission, §6 (cost control) -- real, focused tests for
`api/services/billing_credits.py::enforce_spend_caps`, the new
organization-level daily/monthly spend cap, distinct from
`Credit.balance` insolvency (see that function's own module docstring).
Real DB session, real CreditTransaction rows -- no mocking, matching
this codebase's own established real-infrastructure testing
precedent for billing (tests/test_billing.py)."""

import datetime as dt
import uuid

import pytest

from api.models.billing import Credit, CreditTransaction, CreditTransactionType
from api.services.billing_credits import SpendCapExceededError, enforce_spend_caps


async def _make_org_with_spend(db_session, *, spent_today: int = 0, spent_last_month: int = 0) -> uuid.UUID:
    org_id = uuid.uuid4()
    db_session.add(Credit(organization_id=org_id, balance=10_000))
    await db_session.flush()
    now = dt.datetime.now(dt.timezone.utc)
    if spent_today:
        db_session.add(CreditTransaction(
            organization_id=org_id, type=CreditTransactionType.consume, amount=-spent_today,
            balance_after=10_000 - spent_today, reason="llm_call:test", created_at=now,
        ))
    if spent_last_month:
        last_month = now.replace(day=1) - dt.timedelta(days=1)
        db_session.add(CreditTransaction(
            organization_id=org_id, type=CreditTransactionType.consume, amount=-spent_last_month,
            balance_after=10_000 - spent_last_month, reason="llm_call:test", created_at=last_month,
        ))
    await db_session.commit()
    return org_id


async def test_enforce_spend_caps_is_a_real_no_op_when_no_cap_is_configured(db_session):
    org_id = await _make_org_with_spend(db_session, spent_today=5_000)
    await enforce_spend_caps(db_session, org_id, {"daily_credit_limit": None, "monthly_credit_limit": None})


async def test_enforce_spend_caps_blocks_once_the_real_daily_cap_is_reached(db_session):
    org_id = await _make_org_with_spend(db_session, spent_today=100)
    with pytest.raises(SpendCapExceededError):
        await enforce_spend_caps(db_session, org_id, {"daily_credit_limit": 100, "monthly_credit_limit": None})


async def test_enforce_spend_caps_allows_spend_strictly_under_the_real_daily_cap(db_session):
    org_id = await _make_org_with_spend(db_session, spent_today=50)
    await enforce_spend_caps(db_session, org_id, {"daily_credit_limit": 100, "monthly_credit_limit": None})


async def test_enforce_spend_caps_ignores_real_spend_from_a_previous_calendar_month(db_session):
    """A real spend recorded last month must never count against THIS
    month's real monthly cap -- proves the real UTC calendar-boundary
    logic, not just a rolling N-day window."""
    org_id = await _make_org_with_spend(db_session, spent_last_month=100_000)
    await enforce_spend_caps(db_session, org_id, {"daily_credit_limit": None, "monthly_credit_limit": 1})


async def test_enforce_spend_caps_blocks_once_the_real_monthly_cap_is_reached(db_session):
    org_id = await _make_org_with_spend(db_session, spent_today=200)
    with pytest.raises(SpendCapExceededError):
        await enforce_spend_caps(db_session, org_id, {"daily_credit_limit": None, "monthly_credit_limit": 200})


async def test_enforce_spend_caps_checks_daily_before_monthly(db_session):
    """Both caps configured, daily is the tighter one -- must raise on
    the real daily check without needing the monthly one to also fire."""
    org_id = await _make_org_with_spend(db_session, spent_today=100)
    with pytest.raises(SpendCapExceededError, match="daily cap"):
        await enforce_spend_caps(db_session, org_id, {"daily_credit_limit": 100, "monthly_credit_limit": 100_000})
