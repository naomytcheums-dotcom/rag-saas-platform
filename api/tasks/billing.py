"""Partie 12 -- Celery jobs for billing: monthly invoice generation for
real paid subscriptions, overdue-invoice sweeps, reminder emails, and
credit-alert checks. Same sync-engine pattern as api/tasks/account_purge.py
and api/tasks/compliance.py -- Celery's worker model is sync by default."""

import datetime as dt
import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.billing import Credit, CreditTransaction, CreditTransactionType, Invoice, InvoiceLine, InvoiceStatus
from api.tasks.celery_app import celery_app
from api.tasks._sync_engine import sync_engine as _sync_engine

logger = logging.getLogger(__name__)



@celery_app.task(name="api.tasks.billing.generate_monthly_invoices")
def generate_monthly_invoices() -> int:
    """One real invoice per active, genuinely-paid subscription: a *monthly* subscription is billed for the month just elapsed (never
    for a month before it started); a *yearly* one is billed once per subscription year, for the year starting on its anniversary
    (BILL-010 -- it used to be invoiced the full yearly price every month). A $0 (free) plan never gets an invoice."""
    today = dt.date.today()
    period_end = today.replace(day=1) - dt.timedelta(days=1)
    period_start = period_end.replace(day=1)
    created = 0

    with SyncSession(_sync_engine) as db:
        subs = db.scalars(
            select(Subscription).where(Subscription.status == SubscriptionStatus.active)
        ).all()
        for sub in subs:
            plan = db.get(Plan, sub.plan_id)
            price_cents = (plan.yearly_price_cents if sub.billing_period == "yearly" else plan.monthly_price_cents) if plan else 0
            if not plan or price_cents <= 0:
                continue

            started = sub.created_at.date() if sub.created_at else today
            if sub.billing_period == "yearly":
                invoice_start = _latest_anniversary(started, today)
                invoice_end = _add_years(invoice_start, 1) - dt.timedelta(days=1)
            else:
                if started > period_end:
                    continue  # the subscription began after the month being billed
                invoice_start, invoice_end = period_start, period_end

            already_invoiced = db.scalar(
                select(Invoice.id).where(Invoice.organization_id == sub.organization_id, Invoice.period_start == invoice_start)
            )
            if already_invoiced is not None:
                continue

            vat_cents = round(price_cents * (settings.INVOICE_VAT_RATE / 100))
            invoice = _add_numbered_invoice(
                db, today, organization_id=sub.organization_id, status=InvoiceStatus.pending,
                currency=settings.INVOICE_CURRENCY, subtotal_cents=price_cents, vat_rate=settings.INVOICE_VAT_RATE,
                vat_cents=vat_cents, total_cents=price_cents + vat_cents, period_start=invoice_start,
                period_end=invoice_end, due_date=today + dt.timedelta(days=settings.INVOICE_DUE_DAYS),
            )
            db.add(InvoiceLine(invoice_id=invoice.id, description=f"{plan.name} plan -- {sub.billing_period}", quantity=1, unit_price_cents=price_cents, total_cents=price_cents))
            created += 1
        db.commit()

    logger.info("generate_monthly_invoices: created %d real invoice(s) for period %s..%s", created, period_start, period_end)
    return created


def _add_years(day: dt.date, years: int) -> dt.date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 29 February
        return day.replace(year=day.year + years, day=28)


def _latest_anniversary(start: dt.date, today: dt.date) -> dt.date:
    """The most recent yearly anniversary of `start` that is not after `today` (`start` itself during the first year)."""
    anniversary = start
    while _add_years(anniversary, 1) <= today:
        anniversary = _add_years(anniversary, 1)
    return anniversary


def _add_numbered_invoice(db, today: dt.date, **fields) -> Invoice:
    """Inserts the invoice under the next free number of the year. The number is derived from the highest existing one (not a
    row count) and the insert runs in a savepoint, so two workers racing on the same number retry instead of failing the batch."""
    prefix = f"{settings.INVOICE_PREFIX}-{today.year}-"
    for _attempt in range(5):
        numbers = db.scalars(select(Invoice.number).where(Invoice.number.like(f"{prefix}%"))).all()
        highest = max((int(number[len(prefix):]) for number in numbers if number[len(prefix):].isdigit()), default=0)
        invoice = Invoice(number=f"{prefix}{highest + 1:06d}", **fields)
        try:
            with db.begin_nested():
                db.add(invoice)
                db.flush()
            return invoice
        except IntegrityError:
            continue
    raise RuntimeError("could not allocate an invoice number")


@celery_app.task(name="api.tasks.billing.mark_overdue_invoices")
def mark_overdue_invoices_task() -> int:
    today = dt.date.today()
    with SyncSession(_sync_engine) as db:
        due = db.scalars(
            select(Invoice).where(Invoice.status.in_([InvoiceStatus.sent, InvoiceStatus.pending]), Invoice.due_date < today)
        ).all()
        for invoice in due:
            invoice.status = InvoiceStatus.overdue
        db.commit()
        count = len(due)
    logger.info("mark_overdue_invoices: %d invoice(s) marked overdue", count)
    return count


@celery_app.task(name="api.tasks.billing.send_invoice_reminders")
def send_invoice_reminders() -> int:
    from api.models.organization import OrganizationMember, OrganizationRole
    from api.models.user import User
    from api.services.email_branding import send_branded_invoice_reminder_email_sync

    reminder_days = [int(d) for d in settings.INVOICE_REMINDER_DAYS.split(",") if d.strip()]
    today = dt.date.today()
    sent = 0

    with SyncSession(_sync_engine) as db:
        overdue = db.scalars(select(Invoice).where(Invoice.status == InvoiceStatus.overdue)).all()
        for invoice in overdue:
            days_overdue = (today - invoice.due_date).days if invoice.due_date else 0
            if days_overdue not in reminder_days:
                continue
            owner_email = db.scalar(
                select(User.email).join(OrganizationMember, OrganizationMember.user_id == User.id)
                .where(OrganizationMember.organization_id == invoice.organization_id, OrganizationMember.role == OrganizationRole.owner).limit(1)
            )
            if not owner_email:
                continue
            try:
                send_branded_invoice_reminder_email_sync(db, invoice.organization_id, owner_email, invoice.number, f"{invoice.total_cents / 100:.2f} {invoice.currency}", days_overdue)
                sent += 1
            except Exception:
                logger.warning("send_invoice_reminders: delivery failed for invoice %s", invoice.number, exc_info=True)

    logger.info("send_invoice_reminders: %d reminder(s) sent", sent)
    return sent


@celery_app.task(name="api.tasks.billing.grant_monthly_plan_credits")
def grant_monthly_plan_credits() -> int:
    """AI Pack -- the recurring counterpart to
    billing_credits.get_or_create_credit's one-time signup grant: every
    org with an active subscription on a plan that includes
    `monthly_credits_included` gets that many credits added, once per
    real calendar month. Idempotent the same way generate_monthly_invoices
    above already is -- a `reason` tag naming this exact month lets a
    re-run (a retried Celery task, an accidental second beat trigger)
    find its own prior grant and skip it, rather than double-granting."""
    this_month = dt.date.today().strftime("%Y-%m")
    reason = f"Monthly plan allotment ({this_month})"
    granted = 0

    with SyncSession(_sync_engine) as db:
        subs = db.scalars(select(Subscription).where(Subscription.status == SubscriptionStatus.active)).all()
        for sub in subs:
            plan = db.get(Plan, sub.plan_id)
            if not plan or not plan.monthly_credits_included:
                continue

            already_granted = db.scalar(
                select(CreditTransaction.id).where(
                    CreditTransaction.organization_id == sub.organization_id, CreditTransaction.reason == reason,
                )
            )
            if already_granted is not None:
                continue

            credit = db.scalar(select(Credit).where(Credit.organization_id == sub.organization_id))
            if credit is None:
                credit = Credit(organization_id=sub.organization_id, balance=0)
                db.add(credit)
                db.flush()
            credit.balance += plan.monthly_credits_included
            db.add(CreditTransaction(
                organization_id=sub.organization_id, type=CreditTransactionType.grant,
                amount=plan.monthly_credits_included, balance_after=credit.balance, reason=reason,
            ))
            granted += 1
        db.commit()

    logger.info("grant_monthly_plan_credits: %d organization(s) granted their %s allotment", granted, this_month)
    return granted


@celery_app.task(name="api.tasks.billing.auto_refill_credits")
def auto_refill_credits() -> int:
    """Only real if settings.CREDITS_AUTO_REFILL is on -- honestly a
    no-op (0) otherwise, never silently refilling a balance nobody
    asked this deployment to auto-manage."""
    if not settings.CREDITS_AUTO_REFILL:
        return 0
    refilled = 0
    with SyncSession(_sync_engine) as db:
        low = db.scalars(select(Credit).where(Credit.balance < settings.CREDITS_REFILL_THRESHOLD)).all()
        for credit in low:
            credit.balance += settings.CREDITS_REFILL_AMOUNT
            refilled += 1
        db.commit()
    logger.info("auto_refill_credits: %d organization(s) refilled", refilled)
    return refilled
