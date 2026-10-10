"""BILL-011 / BILL-020: credit amounts are validated and every balance movement leaves a ledger row (SQLite; the row-lock proof is
tests/test_postgres_credits_concurrency.py on a disposable PostgreSQL)."""

import uuid

import pytest
from sqlalchemy import func, select

from api.models.billing import Credit, CreditTransaction
from api.services.billing_credits import add_credits, deduct_credits, refund_credits


async def _fund(db_session, balance: int = 100) -> uuid.UUID:
    org_id = uuid.uuid4()
    db_session.add(Credit(organization_id=org_id, balance=balance))
    await db_session.commit()
    return org_id


async def _balance_and_ledger(db_session, org_id):
    db_session.expire_all()
    balance = await db_session.scalar(select(Credit.balance).where(Credit.organization_id == org_id))
    ledger = await db_session.scalar(select(func.coalesce(func.sum(CreditTransaction.amount), 0)).where(CreditTransaction.organization_id == org_id))
    return balance, ledger


@pytest.mark.parametrize("operation", ["deduct", "add", "refund"])
async def test_a_negative_amount_is_refused_and_changes_nothing(db_session, operation):
    org_id = await _fund(db_session, 100)

    with pytest.raises(ValueError):
        if operation == "deduct":
            await deduct_credits(db_session, org_id, -50, resource_type="exploit")  # used to ADD 50 credits as a "consume" row
        elif operation == "add":
            await add_credits(db_session, org_id, -50, source="exploit")
        else:
            await refund_credits(db_session, org_id, -50, reason="exploit")
    await db_session.rollback()

    balance, ledger = await _balance_and_ledger(db_session, org_id)
    assert balance == 100 and ledger == 0


async def test_sequential_movements_keep_the_balance_equal_to_the_opening_balance_plus_the_ledger(db_session):
    org_id = await _fund(db_session, 100)

    await add_credits(db_session, org_id, 30, source="pack")
    await deduct_credits(db_session, org_id, 10, resource_type="call")
    await refund_credits(db_session, org_id, 5, reason="goodwill")
    await db_session.commit()

    balance, ledger = await _balance_and_ledger(db_session, org_id)
    assert balance == 100 + 30 - 10 + 5 and ledger == 30 - 10 + 5
