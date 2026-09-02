"""
Partie 1.4.1 -- custom domains (e.g. app.ma-boite.com) an organization
can point at this platform. NOT auto-created at organization creation
(unlike quotas/settings/branding) -- a domain is an explicit action an
Owner takes when they have one, not something every organization needs
a default row for.

`status` is a plain String, not a native Postgres enum -- same
reasoning as AuditLog.action (api/models/audit_log.py): a fixed,
app-level StrEnum (CustomDomainStatus below) that never needs a
migration to extend, and avoids the native-enum creation-order traps
this project has already hit twice this session (password_history's
Identity() column, invitations' enum reuse needing the dialect-specific
postgresql.ENUM).

**`ssl_cert`/`ssl_key` are schema placeholders for Partie 1.4.3
(SSL auto via Let's Encrypt), not used by anything in Partie 1.4.1** --
no code path in this step ever writes to them, so they stay NULL for
every domain this step can create. Kept nullable TEXT exactly as the
spec's column list asks, but flagged here deliberately: storing a real
private key in plaintext TEXT would be a genuine vulnerability the
moment something DOES populate them. When Partie 1.4.3 is built, these
values MUST go through api/security/secret_encryption.py (the same
module already protecting JWTSigningKey/EnterpriseSSOConnection
secrets, audit Categorie 4 items 27/28) before ever being written here
-- never stored raw.
"""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class CustomDomainStatus(StrEnum):
    pending = "pending"
    verified = "verified"
    active = "active"
    failed = "failed"


class CustomDomain(Base):
    __tablename__ = "custom_domains"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CustomDomainStatus.pending.value)
    verification_token: Mapped[str] = mapped_column(String(64), nullable=False)
    # See this module's own docstring -- unused placeholders in this step.
    ssl_cert: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssl_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Partie 1.4.4 -- how many automatic polling attempts this domain
    # has had (the periodic sweep only, via
    # api/security/custom_domains.py's apply_verification_check -- the
    # Owner's manual "verify now" endpoint and the original public
    # token link check immediately and don't touch this counter).
    # created_at (already on this row) is reused as the wall-clock
    # timeout anchor -- no separate "first pending at" column needed,
    # since a domain is created directly into `pending` and this
    # project never resets one back to `pending` afterward.
    verification_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_verification_attempt_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("domain", name="uq_custom_domains_domain"),
        # The only read pattern this table serves (list_domains,
        # get_org_domain) is always "this org's rows" -- never `domain`
        # alone across all organizations (that lookup goes through the
        # UNIQUE constraint above instead).
        Index("ix_custom_domains_organization_id", "organization_id"),
    )
