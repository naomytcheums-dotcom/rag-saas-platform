"""Partie 12 -- Celery jobs for billing: monthly invoice generation for
real paid subscriptions, overdue-invoice sweeps, reminder emails, and
credit-alert checks. Same sync-engine pattern as api/tasks/account_purge.py
and api/tasks/compliance.py -- Celery's worker model is sync by default."""

import datetime as dt
import logging

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.billing import Credit, Invoice, InvoiceLine, InvoiceStatus
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), pool_pre_ping=True)


@celery_app.task(name="api.tasks.billing.generate_monthly_invoices")
def generate_monthly_invoices() -> int:
    """One real invoice per active, genuinely-paid (monthly_price_cents
    > 0) subscription, for the month just elapsed. A $0 (free) plan
    never gets an invoice -- there is nothing real to bill."""
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

            already_invoiced = db.scalar(
                select(Invoice.id).where(Invoice.organization_id == sub.organization_id, Invoice.period_start == period_start)
            )
            if already_invoiced is not None:
                continue

            existing_count = db.scalar(select(func.count()).select_from(Invoice)) or 0
            number = f"{settings.INVOICE_PREFIX}-{today.year}-{existing_count + 1:06d}"

            vat_cents = round(price_cents * (settings.INVOICE_VAT_RATE / 100))
            invoice = Invoice(
                organization_id=sub.organization_id, number=number, status=InvoiceStatus.pending,
                currency=settings.INVOICE_CURRENCY, subtotal_cents=price_cents, vat_rate=settings.INVOICE_VAT_RATE,
                vat_cents=vat_cents, total_cents=price_cents + vat_cents, period_start=period_start,
                period_end=period_end, due_date=today + dt.timedelta(days=settings.INVOICE_DUE_DAYS),
            )
            db.add(invoice)
            db.flush()
            db.add(InvoiceLine(invoice_id=invoice.id, description=f"{plan.name} plan -- {sub.billing_period}", quantity=1, unit_price_cents=price_cents, total_cents=price_cents))
            created += 1
        db.commit()

    logger.info("generate_monthly_invoices: created %d real invoice(s) for period %s..%s", created, period_start, period_end)
    return created


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
    from api.services.email import send_invoice_reminder_email

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
                send_invoice_reminder_email(owner_email, invoice.number, f"{invoice.total_cents / 100:.2f} {invoice.currency}", days_overdue)
                sent += 1
            except Exception:
                logger.warning("send_invoice_reminders: delivery failed for invoice %s", invoice.number, exc_info=True)

    logger.info("send_invoice_reminders: %d reminder(s) sent", sent)
    return sent


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
