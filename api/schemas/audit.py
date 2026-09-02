"""Request/response bodies for api/routers/audit.py (audit findings 19/20)."""

import datetime as dt
import uuid

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    """One row of GET /account/audit-logs or GET /admin/audit-logs.
    `checksum` is deliberately never exposed here -- knowing it wouldn't
    let a caller do anything except attempt to forge a chain (impossible
    without AUDIT_LOG_HMAC_SECRET_KEY, but there's no reason to hand out
    the one piece of data any tampering attempt would need)."""

    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    ip: str | None
    user_agent: str | None
    timestamp: dt.datetime
    metadata: dict | None
    success: bool
    failure_reason: str | None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int
    limit: int
    offset: int


class FailedLoginCount(BaseModel):
    key: str  # an IP address or an email, depending on which list this appears in
    count: int


class FailedLoginStatsResponse(BaseModel):
    """GET /admin/failed-logins -- audit finding 20."""

    window_minutes: int
    total_failed_attempts: int
    by_ip: list[FailedLoginCount]
    by_email: list[FailedLoginCount]


class AuditLogIntegrityResponse(BaseModel):
    """GET /admin/audit-logs/verify-integrity -- audit finding 18's
    tamper-evidence, made checkable on demand rather than only ever
    trusted blindly."""

    intact: bool
    first_tampered_entry_id: uuid.UUID | None


class JWTSigningKeyEntry(BaseModel):
    """One row of GET /admin/jwt-keys (audit finding 28) -- the secret
    itself is never included, deliberately (see api/routers/audit.py's
    docstring on this endpoint): this exists purely so an operator can
    SEE that rotation is actually happening and when, not to expose any
    key material."""

    id: uuid.UUID
    is_active: bool
    created_at: dt.datetime
    retired_at: dt.datetime | None

    model_config = {"from_attributes": True}


class JWTSigningKeyListResponse(BaseModel):
    items: list[JWTSigningKeyEntry]
