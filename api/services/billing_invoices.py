"""Partie 12.4 -- invoices. PDF generation reuses the exact lazy-import
weasyprint pattern already established by
api/services/conversation_export.py's export_to_pdf (same honest
"unavailable without native Pango/cairo/GObject libs" handling)."""

import datetime as dt
import logging
import uuid

from sqlalchemy import func, select
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


class PDFUnavailableError(InvoiceError):
    pass


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


async def get_invoice(db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    invoice = await db.get(Invoice, invoice_id)
    if invoice is None or invoice.organization_id != organization_id:
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
    from api.services.email import send_invoice_email

    invoice = await get_invoice(db, organization_id, invoice_id)
    owner_email = await _owner_email(db, organization_id)
    org = await db.get(Organization, organization_id)
    if owner_email:
        try:
            send_invoice_email(owner_email, invoice.number, f"{invoice.total_cents / 100:.2f} {invoice.currency}", org.name if org else "")
        except Exception:
            logger.warning("send_invoice: email delivery failed for invoice %s", invoice.number, exc_info=True)
    invoice.status = InvoiceStatus.sent
    await db.flush()
    return invoice


async def remind_invoice(db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    from api.services.email import send_invoice_reminder_email

    invoice = await get_invoice(db, organization_id, invoice_id)
    owner_email = await _owner_email(db, organization_id)
    days_overdue = (dt.date.today() - invoice.due_date).days if invoice.due_date else 0
    if owner_email:
        try:
            send_invoice_reminder_email(owner_email, invoice.number, f"{invoice.total_cents / 100:.2f} {invoice.currency}", max(days_overdue, 0))
        except Exception:
            logger.warning("remind_invoice: email delivery failed for invoice %s", invoice.number, exc_info=True)
    return invoice


async def mark_invoice_paid(db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    invoice = await get_invoice(db, organization_id, invoice_id)
    invoice.status = InvoiceStatus.paid
    invoice.paid_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return invoice


async def void_invoice(db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID, *, reason: str | None) -> Invoice:
    invoice = await get_invoice(db, organization_id, invoice_id)
    invoice.status = InvoiceStatus.void
    invoice.voided_at = dt.datetime.now(dt.timezone.utc)
    invoice.void_reason = reason
    await db.flush()
    return invoice


async def mark_overdue_invoices(db: AsyncSession) -> int:
    today = dt.date.today()
    due = list((await db.scalars(
        select(Invoice).where(Invoice.status.in_([InvoiceStatus.sent, InvoiceStatus.pending]), Invoice.due_date < today)
    )).all())
    for invoice in due:
        invoice.status = InvoiceStatus.overdue
    await db.flush()
    return len(due)


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

    rows_html = "".join(
        f"<tr><td>{ln.description}</td><td style='text-align:right'>{ln.quantity}</td>"
        f"<td style='text-align:right'>{ln.unit_price_cents / 100:.2f}</td>"
        f"<td style='text-align:right'>{ln.total_cents / 100:.2f}</td></tr>"
        for ln in lines
    )
    html_document = f"""
    <html><head><meta charset="utf-8"><title>{invoice.number}</title></head>
    <body style="font-family: sans-serif;">
      <h1>Invoice {invoice.number}</h1>
      <p>{org.name if org else ''}</p>
      <p>Status: {invoice.status.value} &middot; Due: {invoice.due_date}</p>
      <table style="width:100%; border-collapse: collapse;" border="1" cellpadding="6">
        <thead><tr><th>Description</th><th>Qty</th><th>Unit price</th><th>Total</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      <p style="text-align:right;">Subtotal: {invoice.subtotal_cents / 100:.2f} {invoice.currency}<br/>
      VAT ({invoice.vat_rate}%): {invoice.vat_cents / 100:.2f} {invoice.currency}<br/>
      <strong>Total: {invoice.total_cents / 100:.2f} {invoice.currency}</strong></p>
    </body></html>
    """
    return weasyprint.HTML(string=html_document).write_pdf()


async def _owner_email(db: AsyncSession, organization_id: uuid.UUID) -> str | None:
    row = await db.execute(
        select(User.email)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .where(OrganizationMember.organization_id == organization_id, OrganizationMember.role == OrganizationRole.owner)
        .limit(1)
    )
    return row.scalar()
