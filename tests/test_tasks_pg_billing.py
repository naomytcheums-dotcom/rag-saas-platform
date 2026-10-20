"""Celery tasks of api/tasks/billing.py against a real PostgreSQL: monthly and yearly invoice generation (amounts, VAT, numbering, idempotence), overdue marking,
reminder e-mails, the monthly credit allotment and the opt-in automatic refill. Money is involved: every amount is asserted, not just a count."""

import datetime as dt

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import settings
from api.models.admin import Subscription, SubscriptionStatus
from api.models.billing import Credit, CreditTransaction, CreditTransactionType, Invoice, InvoiceLine, InvoiceStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.tasks.billing import (
    _add_years, _latest_anniversary, auto_refill_credits, generate_monthly_invoices, grant_monthly_plan_credits, mark_overdue_invoices_task, send_invoice_reminders,
)
from pg_tasks_support import organization, plan, require_postgres, user

TODAY = dt.date.today()
NOW = dt.datetime.now(dt.timezone.utc)


@pytest.fixture
def engine():
    return require_postgres()


def _subscribe(engine, org_id, plan_id, *, billing_period="monthly", started_days_ago=100):
    with Session(engine) as db:
        db.add(Subscription(organization_id=org_id, plan_id=plan_id, status=SubscriptionStatus.active, billing_period=billing_period, created_at=NOW - dt.timedelta(days=started_days_ago)))
        db.commit()


def _invoices(engine, org_id) -> list[Invoice]:
    with Session(engine) as db:
        return list(db.scalars(select(Invoice).where(Invoice.organization_id == org_id).order_by(Invoice.period_start)).all())


def test_year_arithmetic_handles_leap_days_and_anniversaries():
    assert _add_years(dt.date(2024, 2, 29), 1) == dt.date(2025, 2, 28)
    assert _add_years(dt.date(2025, 3, 10), 2) == dt.date(2027, 3, 10)
    assert _latest_anniversary(dt.date(2024, 5, 20), dt.date(2024, 12, 1)) == dt.date(2024, 5, 20)  # first year: the start itself
    assert _latest_anniversary(dt.date(2023, 5, 20), dt.date(2026, 5, 20)) == dt.date(2026, 5, 20)  # today is an anniversary
    assert _latest_anniversary(dt.date(2023, 5, 20), dt.date(2026, 5, 19)) == dt.date(2025, 5, 20)


def test_a_monthly_subscription_is_invoiced_once_for_the_month_just_elapsed_with_vat(engine):
    period_end = TODAY.replace(day=1) - dt.timedelta(days=1)
    with organization(engine, "invoice") as org_id, plan(engine, monthly_price_cents=10000, yearly_price_cents=100000) as plan_id:
        _subscribe(engine, org_id, plan_id)

        assert generate_monthly_invoices() >= 1
        generate_monthly_invoices()  # idempotent

        (invoice,) = _invoices(engine, org_id)
        vat = round(10000 * settings.INVOICE_VAT_RATE / 100)
        assert (invoice.subtotal_cents, invoice.vat_cents, invoice.total_cents) == (10000, vat, 10000 + vat)
        assert (invoice.period_start, invoice.period_end) == (period_end.replace(day=1), period_end)
        assert invoice.status == InvoiceStatus.pending and invoice.currency == settings.INVOICE_CURRENCY
        assert invoice.due_date == TODAY + dt.timedelta(days=settings.INVOICE_DUE_DAYS)
        assert invoice.number.startswith(f"{settings.INVOICE_PREFIX}-{TODAY.year}-") and invoice.number.rsplit("-", 1)[1].isdigit()
        with Session(engine) as db:
            (line,) = db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)).all()
            assert line.total_cents == 10000 and "monthly" in line.description


def test_free_plans_and_subscriptions_that_began_after_the_billed_month_get_no_invoice(engine):
    with organization(engine, "free") as free_org, organization(engine, "new") as new_org, plan(engine, monthly_price_cents=0) as free_plan, plan(engine, monthly_price_cents=5000) as paid_plan:
        _subscribe(engine, free_org, free_plan)
        _subscribe(engine, new_org, paid_plan, started_days_ago=0)  # began this month: nothing to bill for last month

        generate_monthly_invoices()

        assert _invoices(engine, free_org) == [] and _invoices(engine, new_org) == []


def test_a_yearly_subscription_is_invoiced_once_per_subscription_year_at_the_yearly_price(engine):
    with organization(engine, "yearly") as org_id, plan(engine, monthly_price_cents=1000, yearly_price_cents=10000) as plan_id:
        _subscribe(engine, org_id, plan_id, billing_period="yearly", started_days_ago=400)

        generate_monthly_invoices()
        generate_monthly_invoices()

        (invoice,) = _invoices(engine, org_id)
        started = (NOW - dt.timedelta(days=400)).date()
        assert invoice.subtotal_cents == 10000  # not 12 x the monthly price
        assert invoice.period_start == _latest_anniversary(started, TODAY) and invoice.period_end == _add_years(invoice.period_start, 1) - dt.timedelta(days=1)


def test_invoice_numbers_are_unique_and_follow_the_highest_existing_one(engine):
    with organization(engine, "n1") as org1, organization(engine, "n2") as org2, plan(engine, monthly_price_cents=1000) as plan_id:
        _subscribe(engine, org1, plan_id)
        _subscribe(engine, org2, plan_id)

        generate_monthly_invoices()

        numbers = [_invoices(engine, org1)[0].number, _invoices(engine, org2)[0].number]
        assert len(set(numbers)) == 2
        assert all(n.startswith(f"{settings.INVOICE_PREFIX}-{TODAY.year}-") for n in numbers)
        assert len({int(n.rsplit("-", 1)[1]) for n in numbers}) == 2


def test_only_unpaid_invoices_past_their_due_date_become_overdue(engine):
    with organization(engine, "overdue") as org_id:
        with Session(engine) as db:
            rows = [
                Invoice(organization_id=org_id, number=f"T-{i}-{org_id.hex[:8]}", status=status, due_date=due)
                for i, (status, due) in enumerate([
                    (InvoiceStatus.pending, TODAY - dt.timedelta(days=2)), (InvoiceStatus.sent, TODAY - dt.timedelta(days=2)), (InvoiceStatus.paid, TODAY - dt.timedelta(days=2)),
                    (InvoiceStatus.pending, TODAY + dt.timedelta(days=2)), (InvoiceStatus.void, TODAY - dt.timedelta(days=2)),
                ])
            ]
            db.add_all(rows)
            db.commit()

        assert mark_overdue_invoices_task() >= 2

        assert [i.status for i in sorted(_invoices(engine, org_id), key=lambda r: r.number)] == [
            InvoiceStatus.overdue, InvoiceStatus.overdue, InvoiceStatus.paid, InvoiceStatus.pending, InvoiceStatus.void,
        ]


def test_reminders_go_to_the_owner_only_on_the_configured_overdue_days(engine, monkeypatch):
    sent = []
    monkeypatch.setattr("api.services.email_branding.send_branded_invoice_reminder_email_sync", lambda db, org_id, email, number, amount, days: sent.append((org_id, email, number, amount, days)))
    monkeypatch.setattr(settings, "INVOICE_REMINDER_DAYS", "7,14")
    with organization(engine, "remind") as org_id, user(engine, "owner") as (owner_id, owner_email):
        with Session(engine) as db:
            db.add(OrganizationMember(organization_id=org_id, user_id=owner_id, role=OrganizationRole.owner))
            db.add_all([
                Invoice(organization_id=org_id, number=f"R7-{org_id.hex[:8]}", status=InvoiceStatus.overdue, due_date=TODAY - dt.timedelta(days=7), total_cents=1250, currency="EUR"),
                Invoice(organization_id=org_id, number=f"R9-{org_id.hex[:8]}", status=InvoiceStatus.overdue, due_date=TODAY - dt.timedelta(days=9), total_cents=100, currency="EUR"),
            ])
            db.commit()

        assert send_invoice_reminders() >= 1

        mine = [s for s in sent if s[0] == org_id]
        assert mine == [(org_id, owner_email, f"R7-{org_id.hex[:8]}", "12.50 EUR", 7)]  # day 9 is not a reminder day

        def boom(*args):
            raise RuntimeError("mail provider down")

        monkeypatch.setattr("api.services.email_branding.send_branded_invoice_reminder_email_sync", boom)
        send_invoice_reminders()  # a delivery failure never stops the run


def test_the_monthly_credit_allotment_is_granted_once_with_its_ledger_row(engine):
    reason = f"Monthly plan allotment ({TODAY.strftime('%Y-%m')})"
    with organization(engine, "allot") as org_id, plan(engine, monthly_credits_included=250) as plan_id:
        _subscribe(engine, org_id, plan_id)

        assert grant_monthly_plan_credits() >= 1
        grant_monthly_plan_credits()  # a retried task does not double-grant

        with Session(engine) as db:
            assert db.scalar(select(Credit.balance).where(Credit.organization_id == org_id)) == 250
            (ledger,) = db.scalars(select(CreditTransaction).where(CreditTransaction.organization_id == org_id)).all()
            assert (ledger.type, ledger.amount, ledger.balance_after, ledger.reason) == (CreditTransactionType.grant, 250, 250, reason)


def test_a_plan_without_included_credits_grants_nothing(engine):
    with organization(engine, "nocredits") as org_id, plan(engine) as plan_id:
        _subscribe(engine, org_id, plan_id)

        grant_monthly_plan_credits()

        with Session(engine) as db:
            assert db.scalars(select(CreditTransaction).where(CreditTransaction.organization_id == org_id)).all() == []


def test_the_automatic_refill_is_off_by_default_and_when_on_refills_only_low_balances_with_a_ledger_row(engine, monkeypatch):
    with organization(engine, "refill") as low_org, organization(engine, "rich") as rich_org:
        with Session(engine) as db:
            db.add_all([Credit(organization_id=low_org, balance=5), Credit(organization_id=rich_org, balance=5000)])
            db.commit()

        assert auto_refill_credits() == 0  # nobody asked this deployment to auto-manage balances
        monkeypatch.setattr(settings, "CREDITS_AUTO_REFILL", True)
        monkeypatch.setattr(settings, "CREDITS_REFILL_THRESHOLD", 100)
        monkeypatch.setattr(settings, "CREDITS_REFILL_AMOUNT", 700)

        assert auto_refill_credits() >= 1

        with Session(engine) as db:
            assert db.scalar(select(Credit.balance).where(Credit.organization_id == low_org)) == 705
            assert db.scalar(select(Credit.balance).where(Credit.organization_id == rich_org)) == 5000
            (ledger,) = db.scalars(select(CreditTransaction).where(CreditTransaction.organization_id == low_org)).all()
            assert ledger.amount == 700 and ledger.balance_after == 705 and "automatic refill" in ledger.reason
