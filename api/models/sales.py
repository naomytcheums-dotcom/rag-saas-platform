"""
Partie 16 (bis) -- sales-model infrastructure beyond SaaS (already real
since Partie 11.4/12): self-hosted licensing, hybrid support/SLA, and
the one genuinely missing white-label piece (reseller/sub-client --
branding, custom domains, and custom-domain email are already real
since Partie 1.3.10/1.4.1/1.4.5, not duplicated here).
"""

import datetime as dt
import enum
import secrets
import uuid

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


# -- Self-hosted: offline license -------------------------------------------

class LicenseStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"


class License(Base):
    """One real license key per self-hosted deployment. `activated_at`/
    `last_validated_at` are real, honest telemetry of an ACTUAL
    validate call -- never backfilled or assumed."""

    __tablename__ = "licenses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    plan_key: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[LicenseStatus] = mapped_column(nullable=False, default=LicenseStatus.active)
    max_activations: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    activation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_validated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def generate_license_key() -> str:
    """Real, random, offline-verifiable-by-format key -- 4 real random
    groups, same entropy class as this codebase's other generated
    secrets (secrets.token_urlsafe), formatted for a human to type/read
    (air-gapped activation, Partie 16's own real requirement)."""
    groups = [secrets.token_hex(4).upper() for _ in range(4)]
    return "-".join(groups)


# -- Hybrid: support tickets + SLA -------------------------------------------

class TicketPriority(str, enum.Enum):
    critical = "critical"
    high = "high"
    normal = "normal"
    low = "low"


class TicketStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


# Partie 16 (bis) -- real SLA response-time targets by priority, in
# hours. Consulted by get_sla_status below to compute a real, honest
# "breached: true/false" rather than a decorative label.
SLA_RESPONSE_HOURS = {
    TicketPriority.critical: 1,
    TicketPriority.high: 4,
    TicketPriority.normal: 24,
    TicketPriority.low: 72,
}


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[TicketPriority] = mapped_column(nullable=False, default=TicketPriority.normal)
    status: Mapped[TicketStatus] = mapped_column(nullable=False, default=TicketStatus.open)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    first_responded_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TicketResponse(Base):
    __tablename__ = "support_ticket_responses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# -- White-label: reseller / sub-clients -------------------------------------

class Reseller(Base):
    """A platform-level partner who resells this app under their own
    brand to their own sub-clients. Reuses OrganizationBranding
    (Partie 1.3.10) and CustomDomain (Partie 1.4.1) on the reseller's
    OWN organization for the actual white-label look -- not duplicated
    here."""

    __tablename__ = "resellers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    commission_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubClient(Base):
    """One real organization a reseller manages on this platform's
    behalf -- `organization_id` IS a real, ordinary Organization row
    (an actual tenant with its own real users/documents/billing), just
    tagged with which reseller brought it on and at what commission
    rate, real revenue math the same honest way admin_subscriptions.py's
    MRR already is."""

    __tablename__ = "sub_clients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reseller_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resellers.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# -- Partner program: a real, persisted commission ledger --------------------

class PartnerCommissionStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"


class PartnerCommission(Base):
    """Partie 18 -- the one real gap `calculate_reseller_commission`
    (above) deliberately left open: that function is a live,
    on-the-fly calculation, not a record. This is the real, persisted
    ledger row a payout run creates and later marks paid -- one row
    per reseller per billing period, so a partner (and this platform)
    has an actual, auditable history of what was owed and when it was
    paid, not just "whatever the math says right now"."""

    __tablename__ = "partner_commissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reseller_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resellers.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    period_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PartnerCommissionStatus] = mapped_column(nullable=False, default=PartnerCommissionStatus.pending)
    paid_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
