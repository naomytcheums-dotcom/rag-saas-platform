"""
Partie 10.3 -- metadata-only records for the encryption subsystem.
Neither table ever stores real key material (that lives only in
ENCRYPTION_MASTER_KEY / ENCRYPTION_MASTER_KEY_PREVIOUS, env-based, see
api/security/encryption.py's own docstring on why this is the one real
mode this environment supports) -- these exist purely so an admin can
see WHEN a rotation happened and what it touched, the same way
api/models/jwt_signing_key.py tracks JWT key rotation history without
ever exposing a JWT secret itself.
"""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class EncryptionKeyRecord(Base):
    """One row per real rotation event -- `label` is an operator-chosen
    free-text note (e.g. "2026-Q3 rotation"), never the key itself."""

    __tablename__ = "encryption_key_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    retired_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EncryptionAudit(Base):
    """One row per real encrypt/rotate operation this module performs --
    an operational log, distinct from api/models/audit_log.py's
    security audit trail (that one tracks WHO did WHAT to WHICH
    resource; this one tracks the encryption subsystem's own internal
    housekeeping, e.g. "rotated 3 webhook secrets")."""

    __tablename__ = "encryption_audit"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)  # "rotate_keys" | "test"
    rows_affected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    performed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
