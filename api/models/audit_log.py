"""
Audit finding 18 -- a persistent, tamper-evident record of sensitive
actions. Distinct from ordinary application `logger.*` calls scattered
through routers (ephemeral, lost on process restart unless shipped to an
external aggregator, and never queryable by the affected user) -- this is
what api/routers/audit.py's GET /account/audit-logs and GET /admin/*
endpoints actually read from.

Tamper-evidence (api/security/audit_log.py's log_audit_action): each row's
`checksum` is a SHA-256 HMAC over its own content chained with the
PREVIOUS row's checksum (using AUDIT_LOG_HMAC_SECRET_KEY, never exposed
via the API) -- altering or deleting any historical row breaks the chain
for every row after it, and forging a new chain from scratch requires the
secret key. verify_audit_log_integrity() walks the chain to detect exactly
that.
"""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AuditAction(StrEnum):
    """Not a DB-level enum (String(100) column below) -- deliberately, so
    a new action never needs a migration to add, only a new value here."""

    REGISTER = "register"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_SET = "password_set"
    TWO_FA_ENABLED = "two_fa_enabled"
    TWO_FA_DISABLED = "two_fa_disabled"
    SESSION_REVOKED = "session_revoked"
    SESSION_IDLE_TIMEOUT = "session_idle_timeout"
    CONCURRENT_SESSION_LIMIT = "concurrent_session_limit"
    ACCOUNT_DELETED = "account_deleted"
    CONSENT_WITHDRAWN = "consent_withdrawn"
    WEBAUTHN_CREDENTIAL_ADDED = "webauthn_credential_added"
    WEBAUTHN_CREDENTIAL_REMOVED = "webauthn_credential_removed"
    WEBAUTHN_LOGIN_SUCCESS = "webauthn_login_success"
    ENTERPRISE_SSO_LOGIN_SUCCESS = "enterprise_sso_login_success"
    ENTERPRISE_SSO_CONNECTION_CREATED = "enterprise_sso_connection_created"
    USER_ROLE_CHANGED = "user_role_changed"
    ORGANIZATION_CREATED = "organization_created"
    ORGANIZATION_DELETED = "organization_deleted"
    ORGANIZATION_MEMBER_ADDED = "organization_member_added"
    ORGANIZATION_MEMBER_ROLE_CHANGED = "organization_member_role_changed"
    ORGANIZATION_MEMBER_REMOVED = "organization_member_removed"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Nullable: a failed login against an unknown email has no real user
    # to attach to -- the attempted email is recorded in `metadata_json`
    # instead, never fabricated into a fake user_id.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6-safe length, same as Session.ip_address
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    # Named metadata_json, not `metadata` -- that name collides with
    # SQLAlchemy's own Base.metadata attribute on every declarative model.
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # See this module's top docstring -- api/security/audit_log.py computes
    # and verifies this, never the caller.
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_user_id_timestamp", "user_id", "timestamp"),
    )
