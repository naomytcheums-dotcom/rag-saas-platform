"""
Partie 12.3 -- credits (a spendable balance) and usage (read via the
real, pre-existing api/security/usage.py ledger, Partie 1.3.8). Credits
and raw usage counting are deliberately kept as two different concerns:
`record_usage` (unchanged, reused as-is) tracks WHAT happened for
traceability; `deduct_credits` here tracks whether the organization can
still afford it.
"""

import datetime as dt
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.billing import Credit, CreditTransaction, CreditTransactionType

logger = logging.getLogger(__name__)


class InsufficientCreditsError(Exception):
    pass


class SpendCapExceededError(Exception):
    """Hardening Mission (§6, cost control) -- raised by
    `enforce_spend_caps` when a real, organization-configured
    `daily_credit_limit`/`monthly_credit_limit` (api/security/
    organization_settings.py) would be exceeded. Deliberately a
    SEPARATE exception from `InsufficientCreditsError`: the organization
    may well still have a positive real `Credit.balance` -- this is an
    owner-chosen burn-rate ceiling, not insolvency."""


async def _real_consumed_since(db: AsyncSession, organization_id: uuid.UUID, since: dt.datetime) -> int:
    """Sums the real, already-applied `consume` transactions
    (`CreditTransaction.amount` is negative for `consume`, see
    `deduct_credits` below) since `since` -- the real, live ledger
    itself is the source of truth, not a separate, driftable counter
    that could fall out of sync with it."""
    total = await db.scalar(
        select(func.coalesce(func.sum(CreditTransaction.amount), 0)).where(
            CreditTransaction.organization_id == organization_id,
            CreditTransaction.type == CreditTransactionType.consume,
            CreditTransaction.created_at >= since,
        )
    )
    return -int(total)  # consume amounts are stored negative; a spend total should read positive


async def enforce_spend_caps(db: AsyncSession, organization_id: uuid.UUID, org_settings: dict) -> None:
    """Hardening Mission (§6, cost control) -- real, pre-flight check
    for the real, organization-configured `daily_credit_limit`/
    `monthly_credit_limit` (`None` = no cap, the default -- see
    api/security/organization_settings.py's own DEFAULT_SETTINGS
    docstring). Call this BEFORE a new real LLM call starts, same
    timing as the pre-existing `Credit.balance` pre-flight check it
    sits next to in `agent_orchestrator.py` -- a cap is only meaningful
    if it stops the spend before it happens, not after.

    Uses real, fixed UTC calendar boundaries (start of today / start of
    this month) -- simple, predictable, and consistent with every other
    UTC-based timestamp in this codebase (no per-organization timezone
    setting is consulted here, even though one exists for display
    purposes, to avoid a cap silently resetting at a different real
    wall-clock moment for every organization)."""
    daily_limit = org_settings.get("daily_credit_limit")
    monthly_limit = org_settings.get("monthly_credit_limit")
    if daily_limit is None and monthly_limit is None:
        return

    now = dt.datetime.now(dt.timezone.utc)
    if daily_limit is not None:
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        spent_today = await _real_consumed_since(db, organization_id, start_of_day)
        if spent_today >= daily_limit:
            raise SpendCapExceededError(f"organization {organization_id} has spent {spent_today} credits today, daily cap is {daily_limit}")

    if monthly_limit is not None:
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        spent_this_month = await _real_consumed_since(db, organization_id, start_of_month)
        if spent_this_month >= monthly_limit:
            raise SpendCapExceededError(f"organization {organization_id} has spent {spent_this_month} credits this month, monthly cap is {monthly_limit}")


async def get_or_create_credit(db: AsyncSession, organization_id: uuid.UUID) -> Credit:
    credit = await db.scalar(select(Credit).where(Credit.organization_id == organization_id))
    if credit is None:
        credit = Credit(organization_id=organization_id, balance=settings.CREDITS_DEFAULT_AMOUNT)
        db.add(credit)
        await db.flush()
        db.add(CreditTransaction(
            organization_id=organization_id, type=CreditTransactionType.grant,
            amount=settings.CREDITS_DEFAULT_AMOUNT, balance_after=credit.balance, reason="Signup allotment",
        ))
        await db.flush()
    return credit


def _check_amount(amount: int) -> None:
    if amount < 0:
        raise ValueError("a credit amount cannot be negative (BILL-020): use the opposite operation instead")


async def _locked_credit(db: AsyncSession, organization_id: uuid.UUID) -> Credit:
    """The organization's balance row, locked (SELECT ... FOR UPDATE) and refreshed: every balance movement starts from the
    committed value, so concurrent credits, refunds and debits cannot overwrite each other (BILL-011)."""
    await get_or_create_credit(db, organization_id)
    credit = await db.scalar(
        select(Credit).where(Credit.organization_id == organization_id).with_for_update().execution_options(populate_existing=True)
    )
    if credit is None:
        raise InsufficientCreditsError(f"organization {organization_id} has no credit account")
    return credit


async def add_credits(db: AsyncSession, organization_id: uuid.UUID, amount: int, *, source: str, user_id: uuid.UUID | None = None) -> Credit:
    _check_amount(amount)
    credit = await _locked_credit(db, organization_id)
    credit.balance += amount
    db.add(CreditTransaction(
        organization_id=organization_id, type=CreditTransactionType.purchase, amount=amount,
        balance_after=credit.balance, reason=source, user_id=user_id,
    ))
    await db.flush()
    return credit


async def grant_credits(db: AsyncSession, organization_id: uuid.UUID, amount: int, *, source: str, user_id: uuid.UUID | None = None) -> Credit:
    """Free credits (promo code, goodwill): same locked balance update as `add_credits`, but recorded as a `grant`, not as a purchase."""
    _check_amount(amount)
    credit = await _locked_credit(db, organization_id)
    credit.balance += amount
    db.add(CreditTransaction(
        organization_id=organization_id, type=CreditTransactionType.grant, amount=amount,
        balance_after=credit.balance, reason=source, user_id=user_id,
    ))
    await db.flush()
    return credit


async def deduct_credits(db: AsyncSession, organization_id: uuid.UUID, amount: int, *, resource_type: str, user_id: uuid.UUID | None = None) -> Credit:
    _check_amount(amount)
    # Refresh the row under a database lock so concurrent debits cannot
    # approve themselves against the same stale balance.
    credit = await _locked_credit(db, organization_id)
    if credit.balance < amount:
        raise InsufficientCreditsError(f"organization {organization_id} has {credit.balance} credits, needs {amount}")
    credit.balance -= amount
    db.add(CreditTransaction(
        organization_id=organization_id, type=CreditTransactionType.consume, amount=-amount,
        balance_after=credit.balance, reason=resource_type, user_id=user_id,
    ))
    await db.flush()
    return credit


async def deduct_credits_up_to(
    db: AsyncSession, organization_id: uuid.UUID, amount: int, *, resource_type: str, user_id: uuid.UUID | None = None,
) -> tuple[Credit, int, int]:
    """BILL-008 -- for a cost that is only known AFTER the (already incurred) provider call: debit `min(balance, amount)`
    so the balance never goes negative and the call is never served for free just because `0 < balance < amount`.
    The uncollected part is written to the ledger row's reason (and logged) -- never silently dropped. Returns
    `(credit, charged, shortfall)`. `deduct_credits` stays the strict, all-or-nothing variant for pre-priced charges."""
    credit = await get_or_create_credit(db, organization_id)
    if amount <= 0:
        return credit, 0, 0
    credit = await db.scalar(
        select(Credit)
        .where(Credit.organization_id == organization_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if credit is None:
        raise InsufficientCreditsError(f"organization {organization_id} has no credit account")
    charged = min(max(credit.balance, 0), amount)
    shortfall = amount - charged
    credit.balance -= charged
    reason = resource_type if shortfall == 0 else f"{resource_type} (partial debit, {shortfall} credits uncollected)"
    db.add(CreditTransaction(
        organization_id=organization_id, type=CreditTransactionType.consume, amount=-charged,
        balance_after=credit.balance, reason=reason[:200], user_id=user_id,
    ))
    await db.flush()
    if shortfall:
        logger.error("organization %s: %s cost %s credits but only %s were available (shortfall %s)", organization_id, resource_type, amount, charged, shortfall)
    return credit, charged, shortfall


async def refund_credits(db: AsyncSession, organization_id: uuid.UUID, amount: int, *, reason: str, user_id: uuid.UUID | None = None) -> Credit:
    _check_amount(amount)
    credit = await _locked_credit(db, organization_id)
    credit.balance += amount
    db.add(CreditTransaction(
        organization_id=organization_id, type=CreditTransactionType.refund, amount=amount,
        balance_after=credit.balance, reason=reason, user_id=user_id,
    ))
    await db.flush()
    return credit


async def list_credit_transactions(db: AsyncSession, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[CreditTransaction]:
    return list((await db.scalars(
        select(CreditTransaction)
        .where(CreditTransaction.organization_id == organization_id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(limit).offset(offset)
    )).all())


async def assert_org_can_spend(
    db: AsyncSession,
    organization_id: uuid.UUID,
    org_settings: dict,
    provider: str,
    *,
    minimum_credits: int = 1,
) -> None:
    """Hardening Mission (§6, cost control) -- the shared pre-flight
    guard for any NEW paid-LLM entry point that doesn't go through
    `AgentOrchestrator` (which has its own, older inline copy of this
    same logic): skipped entirely for a BYOK organization (billed by its
    own provider, never this platform's credits), otherwise a positive
    balance sufficient for `minimum_credits` AND any configured daily/monthly
    spend cap are required.
    Raises `InsufficientCreditsError` / `SpendCapExceededError`."""
    from api.services.llm_byok import resolve_org_api_key

    if await resolve_org_api_key(db, organization_id, provider):
        return
    credit = await get_or_create_credit(db, organization_id)
    if credit.balance < minimum_credits:
        raise InsufficientCreditsError(
            f"organization {organization_id} has {credit.balance} credits, needs {minimum_credits}"
        )
    await enforce_spend_caps(db, organization_id, org_settings)
