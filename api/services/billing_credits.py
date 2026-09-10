"""
Partie 12.3 -- credits (a spendable balance) and usage (read via the
real, pre-existing api/security/usage.py ledger, Partie 1.3.8). Credits
and raw usage counting are deliberately kept as two different concerns:
`record_usage` (unchanged, reused as-is) tracks WHAT happened for
traceability; `deduct_credits` here tracks whether the organization can
still afford it.
"""

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.billing import Credit, CreditTransaction, CreditTransactionType


class InsufficientCreditsError(Exception):
    pass


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


async def add_credits(db: AsyncSession, organization_id: uuid.UUID, amount: int, *, source: str, user_id: uuid.UUID | None = None) -> Credit:
    credit = await get_or_create_credit(db, organization_id)
    credit.balance += amount
    db.add(CreditTransaction(
        organization_id=organization_id, type=CreditTransactionType.purchase, amount=amount,
        balance_after=credit.balance, reason=source, user_id=user_id,
    ))
    await db.flush()
    return credit


async def deduct_credits(db: AsyncSession, organization_id: uuid.UUID, amount: int, *, resource_type: str, user_id: uuid.UUID | None = None) -> Credit:
    credit = await get_or_create_credit(db, organization_id)
    if credit.balance < amount:
        raise InsufficientCreditsError(f"organization {organization_id} has {credit.balance} credits, needs {amount}")
    credit.balance -= amount
    db.add(CreditTransaction(
        organization_id=organization_id, type=CreditTransactionType.consume, amount=-amount,
        balance_after=credit.balance, reason=resource_type, user_id=user_id,
    ))
    await db.flush()
    return credit


async def refund_credits(db: AsyncSession, organization_id: uuid.UUID, amount: int, *, reason: str, user_id: uuid.UUID | None = None) -> Credit:
    credit = await get_or_create_credit(db, organization_id)
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
