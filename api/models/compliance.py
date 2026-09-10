"""
Partie 10.4 -- GDPR/CCPA compliance tracking, additive to the mature
GDPR machinery that already exists on User itself (api/models/user.py's
consent_given_at/consent_withdrawn_at, deletion_scheduled_at) and in
api/services/data_export.py / api/routers/account.py (DELETE /account/me,
GET /account/export, POST /account/consent/withdraw + restore flow).
That existing binary "consent to processing" flag is NOT replaced --
ConsentRecord below is a SEPARATE, per-category axis (marketing,
analytics, cookies, ...) a real product needs beyond the one all-or-
nothing processing consent GDPR Article 6 itself requires to operate
at all.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class DataRequestType(str, enum.Enum):
    access = "access"  # GDPR Art. 15 / CCPA "right to know"
    rectification = "rectification"  # GDPR Art. 16
    erasure = "erasure"  # GDPR Art. 17 / CCPA "right to delete" -- distinct from the existing DELETE /account/me flow: this tracks the REQUEST as a reviewable ticket, not the deletion itself
    restriction = "restriction"  # GDPR Art. 18
    portability = "portability"  # GDPR Art. 20
    objection = "objection"  # GDPR Art. 21


class DataRequestStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    rejected = "rejected"


class DataRequest(Base):
    """A trackable ticket for a user's GDPR/CCPA rights request --
    distinct from the existing DELETE /account/me (which just performs
    an erasure immediately, with its own grace period) because Article
    15/16/18/21 requests are reviewable/actionable by an admin, not a
    one-click self-service action the way deletion and export already
    are."""

    __tablename__ = "data_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    request_type: Mapped[DataRequestType] = mapped_column(Enum(DataRequestType), nullable=False)
    status: Mapped[DataRequestStatus] = mapped_column(Enum(DataRequestStatus), nullable=False, default=DataRequestStatus.pending)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConsentRecord(Base):
    """Per-category consent (e.g. "marketing", "analytics", "cookies")
    -- each row is one real grant-or-withdraw EVENT, not a single mutable
    row per category, so a user's full consent history stays auditable
    (mirrors why api/models/audit_log.py is append-only rather than a
    single "current state" row per user)."""

    __tablename__ = "consent_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    consent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    granted: Mapped[bool] = mapped_column(nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    # Real, deliberate: a Python-generated default (microsecond
    # resolution on every dialect), not `server_default=func.now()` --
    # SQLite's CURRENT_TIMESTAMP is only SECOND-resolution, which made
    # two consent events for the same user in the same request-response
    # cycle (grant, then withdraw) tie exactly, making "the latest row
    # per consent_type" (get_user_consents) genuinely ambiguous. Caught
    # by this module's own tests.
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc), index=True)


class DataBreach(Base):
    """A declared security incident -- GDPR Art. 33/34 requires
    notifying the supervisory authority within 72h and affected users
    "without undue delay"; `notified_at` records when
    api/tasks/compliance.py's send_data_breach_notifications actually
    sent that notice, so `notified_at - created_at` is the real,
    auditable proof of how quickly it happened."""

    __tablename__ = "data_breaches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_user_count: Mapped[int] = mapped_column(nullable=False, default=0)
    declared_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
