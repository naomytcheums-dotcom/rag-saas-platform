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

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
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
    # Partie 1.4.5 -- custom email-sending domain (e.g. contact@ma-boite.com).
    # A SEPARATE verification track from `status` above: a domain can be
    # `active` for hosting (1.4.1/1.4.4) without ever being set up for
    # email, or vice versa -- the two are independent capabilities of the
    # same domain, not a shared state machine.
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Our OWN self-generated DKIM keypair (api/security/email_domains.py's
    # generate_dkim_keys, RSA 2048) -- kept for real, testable DKIM
    # infrastructure exactly as this step's spec asks, but see that
    # module's own docstring for why this is NOT what actually signs
    # outgoing mail: every email this app sends goes through Resend's API
    # (api/services/email.py), and Resend generates and manages its OWN
    # DKIM key server-side (fixed selector "resend"), never accepting a
    # caller-supplied key. dkim_private_key is Fernet-encrypted via
    # api/security/secret_encryption.py (same module as the SSL/ACME
    # keys, Partie 1.4.3) and, like those, never returned by any API response.
    dkim_selector: Mapped[str | None] = mapped_column(String(63), nullable=True)
    dkim_private_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    dkim_public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Proves control of the domain for EMAIL specifically, via a
    # dedicated `_rag-verify.<domain>` TXT record -- a separate token/
    # subdomain from `verification_token`/`_rag-saas-verify` above so the
    # two verification tracks never share a challenge.
    email_verification_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_verification_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    email_verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Not in this step's literal column list, but necessary to make it
    # actually work -- added deliberately, documented here rather than
    # silently: EMAIL_DOMAIN_VERIFICATION_TIMEOUT_HOURS needs a start
    # timestamp to measure from, and unlike 1.4.4's hosting verification
    # (which starts the instant the row is created), email verification
    # is opt-in and may begin long after the domain itself was added --
    # so `created_at` isn't a usable anchor here the way it was there.
    # Set once, the first time email verification setup runs (see
    # api/security/email_domains.py's ensure_email_domain_setup).
    email_verification_started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Also not in the literal column list, also necessary: correlates
    # this row to the real Resend Domain object api/services/
    # resend_domains.py's create_resend_domain registers (Resend's own
    # id, not ours) -- required to later fetch its real DNS records or
    # trigger Resend's own async verification for the SAME domain.
    resend_domain_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
