"""Partie 12.4 -- invoices. PDF generation reuses the exact lazy-import
weasyprint pattern already established by
api/services/conversation_export.py's export_to_pdf (same honest
"unavailable without native Pango/cairo/GObject libs" handling)."""

import asyncio
import datetime as dt
import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.billing import Invoice, InvoiceLine, InvoiceStatus
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User

logger = logging.getLogger(__name__)


class InvoiceError(Exception):
    pass


class InvoiceNotFoundError(InvoiceError):
    pass


class InvoiceStateError(InvoiceError):
    """The requested transition is not allowed from the invoice's current status (BILL-002)."""

    def __init__(self, current: InvoiceStatus, requested: str):
        super().__init__(f"An invoice that is {current.value} cannot be {requested}")
        self.current = current
        self.requested = requested


class PDFUnavailableError(InvoiceError):
    pass


async def audit_invoice_transition(db: AsyncSession, *, user_id: uuid.UUID, ip: str | None, user_agent: str | None, invoice: Invoice, operation: str, before: InvoiceStatus, reason: str | None = None, reference: str | None = None) -> None:
    """BILL-002 / V9: marking an invoice paid or voiding it is a financial act: who, on which organization, from which status to which."""
    from api.models.audit_log import AuditAction
    from api.security.audit_log import log_audit_action
    from api.security.logging_correlation import get_request_id

    await log_audit_action(
        db, user_id=user_id, action=AuditAction.INVOICE_MARKED_PAID if operation == "paid" else AuditAction.INVOICE_VOIDED, ip=ip, user_agent=user_agent,
        success=True, organization_id=invoice.organization_id, resource_type="invoice", resource_id=str(invoice.id),
        metadata={
            "number": invoice.number, "before": before.value, "after": invoice.status.value, "total_cents": invoice.total_cents, "currency": invoice.currency,
            "request_id": get_request_id(), **({"reason": reason} if reason else {}), **({"reference": reference} if reference else {}),
        },
    )


async def generate_invoice_number(db: AsyncSession) -> str:
    """A real sequential number, not a random id -- INV-<year>-<seq>.
    Reads the current count, same check-then-write tolerance this
    codebase already accepts elsewhere (api/security/quotas.py,
    api/security/usage.py) for infrequent, admin-triggered writes."""
    year = dt.datetime.now(dt.timezone.utc).year
    count = await db.scalar(select(func.count()).select_from(Invoice)) or 0
    return f"{settings.INVOICE_PREFIX}-{year}-{count + 1:06d}"


async def calculate_invoice_totals(lines: list[dict], vat_rate: float) -> dict:
    subtotal = sum(line["quantity"] * line["unit_price_cents"] for line in lines)
    vat_cents = round(subtotal * (vat_rate / 100))
    return {"subtotal_cents": subtotal, "vat_cents": vat_cents, "total_cents": subtotal + vat_cents}


async def create_invoice(
    db: AsyncSession, organization_id: uuid.UUID, *, lines: list[dict],
    vat_rate: float | None = None, period_start: dt.date | None = None, period_end: dt.date | None = None,
) -> Invoice:
    vat_rate = settings.INVOICE_VAT_RATE if vat_rate is None else vat_rate
    totals = await calculate_invoice_totals(lines, vat_rate)
    number = await generate_invoice_number(db)
    invoice = Invoice(
        organization_id=organization_id, number=number, status=InvoiceStatus.draft,
        currency=settings.INVOICE_CURRENCY, subtotal_cents=totals["subtotal_cents"], vat_rate=vat_rate,
        vat_cents=totals["vat_cents"], total_cents=totals["total_cents"], period_start=period_start,
        period_end=period_end, due_date=dt.date.today() + dt.timedelta(days=settings.INVOICE_DUE_DAYS),
    )
    db.add(invoice)
    await db.flush()
    for line in lines:
        db.add(InvoiceLine(
            invoice_id=invoice.id, description=line["description"], quantity=line["quantity"],
            unit_price_cents=line["unit_price_cents"], total_cents=line["quantity"] * line["unit_price_cents"],
        ))
    await db.flush()
    return invoice


async def list_invoices(db: AsyncSession, organization_id: uuid.UUID, *, status_filter: InvoiceStatus | None = None, limit: int = 50, offset: int = 0) -> list[Invoice]:
    stmt = select(Invoice).where(Invoice.organization_id == organization_id)
    if status_filter is not None:
        stmt = stmt.where(Invoice.status == status_filter)
    stmt = stmt.order_by(Invoice.created_at.desc()).limit(limit).offset(offset)
    return list((await db.scalars(stmt)).all())


async def get_invoice(db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID, *, lock: bool = False) -> Invoice:
    """`lock=True` takes a row lock (SELECT ... FOR UPDATE on PostgreSQL; ignored by SQLite) and refreshes the row, so two concurrent
    transitions on the same invoice are serialized and the second one sees the first one's committed status."""
    if not lock:
        invoice = await db.get(Invoice, invoice_id)
        if invoice is None or invoice.organization_id != organization_id:
            raise InvoiceNotFoundError(str(invoice_id))
        return invoice
    invoice = await db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == organization_id).with_for_update().execution_options(populate_existing=True)
    )
    if invoice is None:
        raise InvoiceNotFoundError(str(invoice_id))
    return invoice


async def get_invoice_lines(db: AsyncSession, invoice_id: uuid.UUID) -> list[InvoiceLine]:
    return list((await db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id))).all())


async def update_invoice(db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID, **fields) -> Invoice:
    invoice = await get_invoice(db, organization_id, invoice_id)
    for key, value in fields.items():
        if value is not None and hasattr(invoice, key):
            setattr(invoice, key, value)
    await db.flush()
    return invoice


async def send_invoice(db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    from api.services.email_branding import send_branded_invoice_email

    invoice = await get_invoice(db, organization_id, invoice_id)
    owner_email = await _owner_email(db, organization_id)
    if owner_email:
        try:
            await send_branded_invoice_email(
                db, organization_id, owner_email, invoice.number,
                f"{invoice.total_cents / 100:.2f} {invoice.currency}",
            )
        except Exception:
            logger.warning("send_invoice: email delivery failed for invoice %s", invoice.number, exc_info=True)
    invoice.status = InvoiceStatus.sent
    await db.flush()
    return invoice


async def remind_invoice(db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    from api.services.email_branding import send_branded_invoice_reminder_email

    invoice = await get_invoice(db, organization_id, invoice_id)
    owner_email = await _owner_email(db, organization_id)
    days_overdue = (dt.date.today() - invoice.due_date).days if invoice.due_date else 0
    if owner_email:
        try:
            await send_branded_invoice_reminder_email(
                db, organization_id, owner_email, invoice.number,
                f"{invoice.total_cents / 100:.2f} {invoice.currency}",
                max(days_overdue, 0),
            )
        except Exception:
            logger.warning("remind_invoice: email delivery failed for invoice %s", invoice.number, exc_info=True)
    return invoice


async def mark_invoice_paid(db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    """paid is terminal: marking a paid invoice again is a no-op (the first paid_at is kept); a void or refunded invoice cannot be paid."""
    invoice = await get_invoice(db, organization_id, invoice_id, lock=True)
    if invoice.status == InvoiceStatus.paid:
        return invoice
    if invoice.status in (InvoiceStatus.void, InvoiceStatus.refunded):
        raise InvoiceStateError(invoice.status, "marked paid")
    invoice.status = InvoiceStatus.paid
    invoice.paid_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return invoice


async def void_invoice(db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID, *, reason: str | None) -> Invoice:
    """A paid invoice can never be voided (that would erase collected revenue; a refund is a separate operation); voiding twice is a no-op."""
    invoice = await get_invoice(db, organization_id, invoice_id, lock=True)
    if invoice.status == InvoiceStatus.void:
        return invoice
    if invoice.status in (InvoiceStatus.paid, InvoiceStatus.refunded):
        raise InvoiceStateError(invoice.status, "voided")
    invoice.status = InvoiceStatus.void
    invoice.voided_at = dt.datetime.now(dt.timezone.utc)
    invoice.void_reason = reason
    await db.flush()
    return invoice


async def settle_invoice(db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID, *, operation: str, reason: str | None, actor_id: uuid.UUID, ip: str | None, user_agent: str | None, reference: str | None = None) -> Invoice:
    """The single entry point for the two privileged invoice transitions (`paid` / `void`): row lock + state machine + audit in the
    caller's transaction. `reference` is the external proof of a manual settlement (bank transfer id, ...), kept in the audit row."""
    before = (await get_invoice(db, organization_id, invoice_id, lock=True)).status
    if operation == "paid":
        invoice = await mark_invoice_paid(db, organization_id, invoice_id)
    else:
        invoice = await void_invoice(db, organization_id, invoice_id, reason=reason)
    if invoice.status != before:  # a repeated call is an idempotent no-op, not a second financial act
        await audit_invoice_transition(db, user_id=actor_id, ip=ip, user_agent=user_agent, invoice=invoice, operation=operation, before=before, reason=reason, reference=reference)
    return invoice


async def mark_overdue_invoices(db: AsyncSession) -> int:
    """One atomic UPDATE restricted to the statuses that may become overdue: a payment committed meanwhile is never overwritten."""
    today = dt.date.today()
    result = await db.execute(
        update(Invoice).where(Invoice.status.in_([InvoiceStatus.sent, InvoiceStatus.pending]), Invoice.due_date < today).values(status=InvoiceStatus.overdue)
    )
    await db.flush()
    return result.rowcount or 0


async def get_invoice_stats(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    total_paid = await db.scalar(select(func.coalesce(func.sum(Invoice.total_cents), 0)).where(Invoice.organization_id == organization_id, Invoice.status == InvoiceStatus.paid)) or 0
    total_outstanding = await db.scalar(select(func.coalesce(func.sum(Invoice.total_cents), 0)).where(Invoice.organization_id == organization_id, Invoice.status.in_([InvoiceStatus.sent, InvoiceStatus.pending, InvoiceStatus.overdue]))) or 0
    overdue_count = await db.scalar(select(func.count()).where(Invoice.organization_id == organization_id, Invoice.status == InvoiceStatus.overdue)) or 0
    return {"total_paid_cents": total_paid, "total_outstanding_cents": total_outstanding, "overdue_count": overdue_count}


async def generate_invoice_pdf(db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID) -> bytes:
    invoice = await get_invoice(db, organization_id, invoice_id)
    lines = await get_invoice_lines(db, invoice_id)
    org = await db.get(Organization, organization_id)

    try:
        import weasyprint
    except OSError as exc:
        raise PDFUnavailableError(
            "PDF generation is unavailable on this deployment: WeasyPrint's native libraries "
            "(Pango/cairo/GObject) are not installed. See requirements-api.txt's own comment."
        ) from exc

    from api.services.pdf_safety import deny_all_url_fetcher, esc

    rows_html = "".join(
        f"<tr><td>{esc(ln.description)}</td><td style='text-align:right'>{ln.quantity}</td>"
        f"<td style='text-align:right'>{ln.unit_price_cents / 100:.2f}</td>"
        f"<td style='text-align:right'>{ln.total_cents / 100:.2f}</td></tr>"
        for ln in lines
    )
    html_document = f"""
    <html><head><meta charset="utf-8"><title>{esc(invoice.number)}</title></head>
    <body style="font-family: sans-serif;">
      <h1>Invoice {esc(invoice.number)}</h1>
      <p>{esc(org.name) if org else ''}</p>
      <p>Status: {esc(invoice.status.value)} &middot; Due: {esc(invoice.due_date)}</p>
      <table style="width:100%; border-collapse: collapse;" border="1" cellpadding="6">
        <thead><tr><th>Description</th><th>Qty</th><th>Unit price</th><th>Total</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      <p style="text-align:right;">Subtotal: {invoice.subtotal_cents / 100:.2f} {esc(invoice.currency)}<br/>
      VAT ({esc(invoice.vat_rate)}%): {invoice.vat_cents / 100:.2f} {esc(invoice.currency)}<br/>
      <strong>Total: {invoice.total_cents / 100:.2f} {esc(invoice.currency)}</strong></p>
    </body></html>
    """
    return weasyprint.HTML(string=html_document, url_fetcher=deny_all_url_fetcher).write_pdf()


async def _owner_email(db: AsyncSession, organization_id: uuid.UUID) -> str | None:
    row = await db.execute(
        select(User.email)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .where(OrganizationMember.organization_id == organization_id, OrganizationMember.role == OrganizationRole.owner)
        .limit(1)
    )
    return row.scalar()
