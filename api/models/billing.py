"""
Partie 12 -- billing. Deliberately does NOT duplicate what already
exists for real elsewhere in this codebase:

- Plan/Subscription -- api/models/admin.py (Partie 11.4), extended here
  with yearly pricing and feature flags (see that module's own diff).
- Per-organization usage counting -- api/models/organization_usage.py +
  api/security/usage.py (Partie 1.3.8) is already a real, generic,
  metric-agnostic usage ledger; credits below are consumed FROM that
  same real data (get_usage), not a second parallel counter.

What's genuinely new: Credit (a spendable balance, distinct from raw
usage counting), CreditTransaction (its audit trail), Invoice/
InvoiceLine (real billing documents), and the minimal payment-provider
bookkeeping (PaymentCustomer, PaymentEvent for webhook idempotency) --
none of which existed anywhere in this codebase before this part.

**Phase 5, Étape 2 (2026-09-22) -- generalized for multi-provider
billing (Stripe + Paystack)**: `StripeCustomer`/`StripeEvent` were
Stripe-only tables, each keyed uniquely on `organization_id` alone --
that made it structurally impossible for an organization to ever have
a real customer record with a second provider. Renamed to
`PaymentCustomer`/`PaymentEvent` with an explicit `provider` column
("stripe" | "paystack") and `organization_id` uniqueness now scoped
per-provider, not global. `PaymentEvent` unique key is a real
`payment_provider_event_uq` covering `(provider, id)` -- Stripe's and
Paystack's own event-id formats already differ in shape (`evt_...` vs
a bare integer), but this makes the impossibility explicit rather than
relying on that never colliding. Migration
0115_generalize_payment_provider_tables.py renames both tables in
place and backfills `provider='stripe'` on every pre-existing row --
reversible, no data loss (see that migration's own docstring).
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class CreditTransactionType(str, enum.Enum):
    purchase = "purchase"
    consume = "consume"
    refund = "refund"
    grant = "grant"  # e.g. the free signup allotment


class Credit(Base):
    __tablename__ = "credits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[CreditTransactionType] = mapped_column(nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # signed: +purchase/+refund/+grant, -consume
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    pending = "pending"
    sent = "sent"
    paid = "paid"
    overdue = "overdue"
    void = "void"
    refunded = "refunded"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(nullable=False, default=InvoiceStatus.draft)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vat_rate: Mapped[Numeric] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    vat_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    period_start: Mapped[dt.date | None] = mapped_column(nullable=True)
    period_end: Mapped[dt.date | None] = mapped_column(nullable=True)
    due_date: Mapped[dt.date | None] = mapped_column(nullable=True)
    paid_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)


class PaymentProvider(str, enum.Enum):
    stripe = "stripe"
    paystack = "paystack"


class PaymentCustomer(Base):
    """One row per (organization, provider) that has ever started a
    real checkout/portal flow with that specific provider -- absent
    entirely for a provider an organization never used, which is every
    provider in this environment today unless a real secret key is
    configured (see api/services/billing_providers/)."""

    __tablename__ = "payment_customers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[PaymentProvider] = mapped_column(nullable=False)
    external_customer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("organization_id", "provider", name="uq_payment_customer_org_provider"),
        UniqueConstraint("provider", "external_customer_id", name="uq_payment_customer_provider_external_id"),
    )


class PaymentEvent(Base):
    """Idempotency ledger for both POST /billing/stripe/webhook and
    POST /billing/paystack/webhook -- both providers' own docs guarantee
    at-least-once delivery, so a webhook handler that doesn't record
    which event ids it already applied WILL double-apply one
    eventually. `id` is the real external event id (Stripe's "evt_...",
    Paystack's own bare integer id as a string), scoped per-provider --
    see this module's own docstring for why a global unique id can't be
    assumed across two independent providers."""

    __tablename__ = "payment_events"

    provider: Mapped[PaymentProvider] = mapped_column(nullable=False, primary_key=True)
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    payload_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class UsageAlert(Base):
    __tablename__ = "usage_alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)  # matches an organization_usage metric name
    threshold_percent: Mapped[int] = mapped_column(Integer, nullable=False)  # e.g. 80 = alert at 80% of the plan limit
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("organization_id", "resource_type", "threshold_percent", name="uq_usage_alert_org_metric_threshold"),
    )
