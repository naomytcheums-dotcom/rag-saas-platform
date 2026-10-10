"""BILL-011 / BILL-020: credit balance integrity on a DISPOSABLE PostgreSQL only (tests/disposable_pg_guard.py: local host, marked database
name, explicit RAG_DISPOSABLE_PG_CONFIRM, not the application's DATABASE_URL; otherwise the module is skipped with the reason).

40 concurrent add_credits(10) and 40 deduct_credits(10), each in its own session/transaction. Without a row lock on the add/refund
path the balance drifts from the ledger (lost updates); with it, balance == starting balance + sum of the ledger movements.
"""

import asyncio
import os
import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.billing import Credit, CreditTransaction
from api.models.organization import Organization
from api.services.billing_credits import add_credits, deduct_credits, get_or_create_credit
from disposable_pg_guard import disposable_pg_refusal

URL = os.environ.get("RAG_DISPOSABLE_PG_URL", "")
_REFUSAL = disposable_pg_refusal(URL, os.environ.get("RAG_DISPOSABLE_PG_CONFIRM"), str(settings.DATABASE_URL), os.environ.get("DATABASE_URL"))

pytestmark = pytest.mark.skipif(_REFUSAL is not None, reason=f"PostgreSQL concurrency tests not authorized: {_REFUSAL}")


async def test_concurrent_credits_and_debits_never_drift_from_the_ledger():
    engine = create_async_engine(URL, pool_size=20)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    tag = uuid.uuid4().hex[:10]
    async with maker() as session:
        org = Organization(name=f"CredConc {tag}", slug=f"credconc-{tag}")
        session.add(org)
        await session.flush()
        credit = await get_or_create_credit(session, org.id)
        credit.balance = 100_000
        await session.commit()
        org_id = org.id

    async def add_one():
        async with maker() as session:
            await add_credits(session, org_id, 10, source="concurrency")
            await session.commit()

    async def deduct_one():
        async with maker() as session:
            await deduct_credits(session, org_id, 10, resource_type="concurrency")
            await session.commit()

    try:
        await asyncio.gather(*([add_one() for _ in range(40)] + [deduct_one() for _ in range(40)]))
        async with maker() as session:
            balance = (await session.scalar(select(Credit.balance).where(Credit.organization_id == org_id)))
            movements = await session.scalar(
                select(func.coalesce(func.sum(CreditTransaction.amount), 0)).where(
                    CreditTransaction.organization_id == org_id, CreditTransaction.reason.in_(("concurrency", "Signup allotment"))
                )
            )
        assert balance == 100_000, f"lost update: balance drifted to {balance}"
        assert movements == settings.CREDITS_DEFAULT_AMOUNT, "the ledger rows are the movements of the run (plus the signup grant)"
    finally:
        async with maker() as session:
            await session.execute(delete(CreditTransaction).where(CreditTransaction.organization_id == org_id))
            await session.execute(delete(Credit).where(Credit.organization_id == org_id))
            await session.execute(delete(Organization).where(Organization.id == org_id))
            await session.commit()
        await engine.dispose()
