"""BILL-010: invoices must match what was sold -- a yearly subscription is invoiced once a year (not its full price every month), a
monthly one is never billed for a month before it started, numbers follow the highest existing number, a free plan is never billed."""

import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.admin import Plan, Subscription, SubscriptionStatus


@pytest.fixture
def invoice_env(monkeypatch):
    """The invoice task uses its own synchronous engine: point it at an in-memory SQLite with the real schema."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from api.database import Base
    from api.tasks import billing as billing_tasks

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(billing_tasks, "_sync_engine", engine)
    with Session(engine) as session:
        yield billing_tasks, session
    engine.dispose()


def _seed_paid_subscription(session, billing_period, created_at):
    plan = Plan(key=f"pro-{uuid.uuid4().hex[:6]}", name="Pro", monthly_price_cents=19900, yearly_price_cents=199000)
    session.add(plan)
    session.flush()
    org_id = uuid.uuid4()
    session.add(Subscription(organization_id=org_id, plan_id=plan.id, status=SubscriptionStatus.active, billing_period=billing_period, created_at=created_at))
    session.commit()
    return org_id


def _run_task(billing_tasks, monkeypatch, today):
    import types

    class _Date(dt.date):
        @classmethod
        def today(cls):
            return today

    # Only the task module's own view of `datetime` is replaced; the global module stays untouched.
    shim = types.SimpleNamespace(date=_Date, timedelta=dt.timedelta, datetime=dt.datetime, timezone=dt.timezone)
    monkeypatch.setattr(billing_tasks, "dt", shim)
    return billing_tasks.generate_monthly_invoices()


def _invoices(session):
    from api.models.billing import Invoice

    session.expire_all()
    return session.scalars(select(Invoice).order_by(Invoice.number)).all()


def test_a_yearly_subscription_is_invoiced_once_a_year_not_every_month(invoice_env, monkeypatch):
    billing_tasks, session = invoice_env
    _seed_paid_subscription(session, "yearly", dt.datetime(2026, 3, 15, tzinfo=dt.timezone.utc))

    first = _run_task(billing_tasks, monkeypatch, dt.date(2026, 4, 2))
    again = _run_task(billing_tasks, monkeypatch, dt.date(2026, 4, 3))
    later_months = [_run_task(billing_tasks, monkeypatch, dt.date(2026, month, 2)) for month in (5, 6, 7, 12)]
    next_year = _run_task(billing_tasks, monkeypatch, dt.date(2027, 4, 2))

    assert (first, again, later_months, next_year) == (1, 0, [0, 0, 0, 0], 1)
    invoices = _invoices(session)
    assert [(i.period_start, i.period_end, i.subtotal_cents) for i in invoices] == [
        (dt.date(2026, 3, 15), dt.date(2027, 3, 14), 199000), (dt.date(2027, 3, 15), dt.date(2028, 3, 14), 199000),
    ]


def test_a_monthly_subscription_is_not_billed_for_a_month_before_it_started(invoice_env, monkeypatch):
    billing_tasks, session = invoice_env
    _seed_paid_subscription(session, "monthly", dt.datetime(2026, 10, 3, tzinfo=dt.timezone.utc))

    assert _run_task(billing_tasks, monkeypatch, dt.date(2026, 10, 5)) == 0  # September: before the subscription existed
    assert _run_task(billing_tasks, monkeypatch, dt.date(2026, 11, 2)) == 1
    invoices = _invoices(session)
    assert [(i.period_start, i.period_end, i.subtotal_cents) for i in invoices] == [(dt.date(2026, 10, 1), dt.date(2026, 10, 31), 19900)]


def test_invoice_numbers_follow_the_highest_existing_number_not_a_row_count(invoice_env, monkeypatch):
    from api.models.billing import Invoice, InvoiceStatus

    billing_tasks, session = invoice_env
    _seed_paid_subscription(session, "monthly", dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))
    _seed_paid_subscription(session, "monthly", dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))
    session.add(Invoice(
        organization_id=uuid.uuid4(), number=f"{settings.INVOICE_PREFIX}-2026-000010", status=InvoiceStatus.paid, currency="EUR",
        subtotal_cents=1, vat_rate=20, vat_cents=0, total_cents=1, period_start=dt.date(2025, 1, 1), period_end=dt.date(2025, 1, 31),
        due_date=dt.date(2025, 2, 1),
    ))
    session.commit()

    assert _run_task(billing_tasks, monkeypatch, dt.date(2026, 6, 2)) == 2
    numbers = sorted(invoice.number for invoice in _invoices(session))
    assert numbers == [f"{settings.INVOICE_PREFIX}-2026-00001{n}" for n in (0, 1, 2)]


def test_a_free_plan_is_never_invoiced(invoice_env, monkeypatch):
    billing_tasks, session = invoice_env
    plan = Plan(key="free-x", name="Free", monthly_price_cents=0, yearly_price_cents=0)
    session.add(plan)
    session.flush()
    session.add(Subscription(organization_id=uuid.uuid4(), plan_id=plan.id, status=SubscriptionStatus.active, billing_period="monthly"))
    session.commit()
    assert _run_task(billing_tasks, monkeypatch, dt.date(2026, 6, 2)) == 0
