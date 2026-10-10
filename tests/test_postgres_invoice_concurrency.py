"""Invoice transitions under real concurrency, on a DISPOSABLE PostgreSQL only (row locks are not provable on SQLite).

Opt-in and guarded (see tests/disposable_pg_guard.py, unit-tested in test_disposable_pg_guard.py). Every condition is required:
RAG_DISPOSABLE_PG_URL points at a LOCAL database whose name contains disposable, roundtrip, scratch or throwaway,
RAG_DISPOSABLE_PG_CONFIRM equals that database name, and the target is not the application's own DATABASE_URL. Otherwise the whole
module is skipped with the reason; nothing is claimed as verified. A local host alone is NOT enough (a tunnel to a shared or real
database is local too).

Each scenario holds the first transaction open (no commit) while a second one starts on the same invoice: without `SELECT ... FOR UPDATE`
the second would read the old status and transition again (two audit rows, or a paid invoice voided).
"""

import asyncio
import os
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.audit_log import AuditLog
from api.models.billing import Invoice, InvoiceStatus
from api.models.organization import Organization
from api.models.user import User, UserRole
from api.services.billing_invoices import InvoiceStateError, create_invoice, settle_invoice
from disposable_pg_guard import disposable_pg_refusal

URL = os.environ.get("RAG_DISPOSABLE_PG_URL", "")
_REFUSAL = disposable_pg_refusal(URL, os.environ.get("RAG_DISPOSABLE_PG_CONFIRM"), str(settings.DATABASE_URL), os.environ.get("DATABASE_URL"))

pytestmark = pytest.mark.skipif(_REFUSAL is not None, reason=f"PostgreSQL concurrency tests not authorized: {_REFUSAL}")


async def _world():
    engine = create_async_engine(URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    tag = uuid.uuid4().hex[:10]
    async with maker() as session:
        user = User(email=f"conc-{tag}@example.com", hashed_password="x", is_email_verified=True, role=UserRole.superadmin)
        org = Organization(name=f"Conc {tag}", slug=f"conc-{tag}")
        session.add_all([user, org])
        await session.flush()
        invoice = await create_invoice(session, org.id, lines=[{"description": "Pro", "quantity": 1, "unit_price_cents": 19900}])
        invoice.status = InvoiceStatus.pending
        await session.commit()
        ids = (user.id, org.id, invoice.id)
    return engine, maker, ids


async def _cleanup(maker, ids):
    user_id, org_id, invoice_id = ids
    async with maker() as session:
        for model, key in ((Invoice, invoice_id), (Organization, org_id), (User, user_id)):
            row = await session.get(model, key)
            if row is not None:
                await session.delete(row)
        await session.commit()


async def _run(maker, ids, operation, *, hold):
    user_id, org_id, invoice_id = ids
    async with maker() as session:
        try:
            invoice = await settle_invoice(session, org_id, invoice_id, operation=operation, reason="r" if operation == "void" else None, actor_id=user_id, ip=None, user_agent=None, reference="REF-1")
        except InvoiceStateError:
            await session.rollback()
            return "refused"
        if hold:
            await asyncio.sleep(0.6)  # the first transaction keeps its lock while the second one starts
        status = invoice.status
        await session.commit()
        return status.value


async def _final(maker, ids):
    async with maker() as session:
        invoice = await session.get(Invoice, ids[2])
        rows = await session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.resource_id == str(ids[2])))
        return invoice.status.value, invoice.paid_at is not None, rows


async def _race(first, second):
    engine, maker, ids = await _world()
    try:
        started = asyncio.create_task(_run(maker, ids, first, hold=True))
        await asyncio.sleep(0.2)
        other = await _run(maker, ids, second, hold=False)
        return await started, other, await _final(maker, ids)
    finally:
        await _cleanup(maker, ids)
        await engine.dispose()


async def test_two_concurrent_payments_apply_once():
    first, second, final = await _race("paid", "paid")
    assert (first, second) == ("paid", "paid")
    assert final == ("paid", True, 1), "one payment, one audit row"


async def test_two_concurrent_voids_apply_once():
    first, second, final = await _race("void", "void")
    assert (first, second) == ("void", "void") and final == ("void", False, 1)


async def test_a_payment_in_flight_blocks_a_concurrent_void():
    first, second, final = await _race("paid", "void")
    assert (first, second) == ("paid", "refused")
    assert final == ("paid", True, 1), "a paid invoice is never voided, even by a concurrent request"


async def test_a_void_in_flight_blocks_a_concurrent_payment():
    first, second, final = await _race("void", "paid")
    assert (first, second) == ("void", "refused")
    assert final == ("void", False, 1)


async def test_the_overdue_sweep_cannot_overwrite_a_payment_that_commits_meanwhile():
    """The sweep is a single conditional UPDATE: a payment committed first keeps its status."""
    from api.services.billing_invoices import mark_overdue_invoices
    import datetime as dt

    engine, maker, ids = await _world()
    try:
        async with maker() as session:
            invoice = await session.get(Invoice, ids[2])
            invoice.due_date = dt.date.today() - dt.timedelta(days=3)
            await session.commit()
        await _run(maker, ids, "paid", hold=False)
        async with maker() as session:
            await mark_overdue_invoices(session)
            await session.commit()
        assert (await _final(maker, ids))[0] == "paid"
    finally:
        await _cleanup(maker, ids)
        await engine.dispose()
