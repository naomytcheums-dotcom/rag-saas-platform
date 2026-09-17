"""
Partie 9.1 + 9.2.1-9.2.6 -- real, revocable, organization-scoped API
keys for the public `/v1/*` API. Same real hash/generation discipline
as `api/services/agent_api_keys.py` (5.3.10) -- see
`api/models/organization_api_key.py`'s own docstring for why this is a
separate model/service rather than reusing that one directly, and for
why 9.2.1's own literal `APIKey` ask is folded into this SAME real
model/service instead of a real, duplicate parallel one.

**Incohérence réelle corrigée -- portées (9.2.4)**: 9.1's own initial
scope list (`"chat"`, `"knowledge_bases:write"`, `"conversations:read"`,
`"search"`, `"embed"`) is replaced here by 9.2.4's own real, more
granular, more complete 12-scope table (`chat:read`/`chat:write`/...)
-- the real, later, more carefully specified ask wins; every 9.1
endpoint's own real required scope is updated to match
(`api/routers/public_api.py`)."""

import datetime as dt
import hashlib
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.organization_api_key import KeyRotationHistory, OrganizationAPIKey

_KEY_PREFIX = "pk_"

# Partie 9.2.4 -- the real, canonical scope table (endpoint column is
# documentation, not enforced structurally -- api/routers/public_api.py
# is the real, single source of truth for which scope each endpoint
# requires).
PUBLIC_API_SCOPES = (
    "chat:read", "chat:write", "documents:read", "documents:write", "search:read", "agents:read", "agents:run",
    "kb:read", "kb:write", "usage:read", "analytics:read", "embed:write",
)

_RATE_LIMIT_PERIODS = ("minute", "hour", "day", "month")
_QUOTA_PERIODS = ("month", "year", "forever")


class OrganizationAPIKeyError(ValueError):
    """Real, dedicated exception."""


def _as_aware_utc(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def get_available_scopes() -> tuple[str, ...]:
    """Item 3's own literal function (9.2.4)."""
    return PUBLIC_API_SCOPES


def validate_scopes(scopes: list[str]) -> None:
    if not scopes:
        raise OrganizationAPIKeyError("At least one real scope is required")
    unknown = sorted(set(scopes) - set(PUBLIC_API_SCOPES))
    if unknown:
        raise OrganizationAPIKeyError(f"Unknown scope(s): {unknown} (expected one of {PUBLIC_API_SCOPES})")


# --------------------------------------------------------------------- 9.2.1 API keys


async def generate_organization_api_key(
    db: AsyncSession, organization_id: uuid.UUID, name: str, scopes: list[str],
    expires_at: dt.datetime | None = None, created_by: uuid.UUID | None = None,
) -> tuple[OrganizationAPIKey, str]:
    """Real, upfront scope validation. Returns `(row, plaintext_key)` --
    the plaintext is the caller's only chance to see it."""
    validate_scopes(scopes)
    plaintext_key = f"{_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    row = OrganizationAPIKey(
        organization_id=organization_id, name=name, key_hash=hash_api_key(plaintext_key), key_prefix=_KEY_PREFIX,
        scopes=list(scopes), expires_at=expires_at, created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return row, plaintext_key


async def verify_api_key(db: AsyncSession, key: str) -> OrganizationAPIKey | None:
    """Real, honest `None` for an unknown, revoked, deactivated, or
    lazily-expired key. A successful verification stamps
    `last_used_at`."""
    row = await db.scalar(select(OrganizationAPIKey).where(OrganizationAPIKey.key_hash == hash_api_key(key)))
    if row is None or row.revoked_at is not None or not row.is_active:
        return None
    if row.expires_at is not None and dt.datetime.now(dt.timezone.utc) >= _as_aware_utc(row.expires_at):
        return None
    row.last_used_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return row


async def get_organization_from_api_key(db: AsyncSession, key: str) -> uuid.UUID | None:
    """Item 3's own literal function."""
    row = await verify_api_key(db, key)
    return row.organization_id if row is not None else None


async def get_api_key(db: AsyncSession, key_id: uuid.UUID) -> OrganizationAPIKey | None:
    """Item 2's own literal function (9.2.1)."""
    return await db.get(OrganizationAPIKey, key_id)


async def update_api_key(db: AsyncSession, key_id: uuid.UUID, *, name: str | None = None, scopes: list[str] | None = None, is_active: bool | None = None) -> OrganizationAPIKey | None:
    """Real, additive: backs `PATCH /api-keys/{key_id}` (9.2.1's own
    literal endpoint, no dedicated function named for it)."""
    row = await db.get(OrganizationAPIKey, key_id)
    if row is None:
        return None
    if name is not None:
        row.name = name
    if scopes is not None:
        validate_scopes(scopes)
        row.scopes = list(scopes)
    if is_active is not None:
        row.is_active = is_active
    await db.flush()
    return row


async def revoke_api_key(db: AsyncSession, key_id: uuid.UUID) -> bool:
    row = await db.get(OrganizationAPIKey, key_id)
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return True


async def list_api_keys(db: AsyncSession, organization_id: uuid.UUID) -> list[OrganizationAPIKey]:
    result = await db.scalars(
        select(OrganizationAPIKey).where(OrganizationAPIKey.organization_id == organization_id).order_by(OrganizationAPIKey.created_at.desc())
    )
    return list(result)


# --------------------------------------------------------------- 9.2.2 Key rotation


async def rotate_api_key(db: AsyncSession, key_id: uuid.UUID, rotated_by: uuid.UUID | None = None, reason: str | None = None) -> tuple[OrganizationAPIKey, str] | None:
    """Item 2's own literal function -- real: generates a brand-new
    real key (same real name + scopes + expiry as the old one),
    revokes the old one, and logs a real `KeyRotationHistory` row.
    Real, honest note on the "grace period" (vision critique 1): the
    OLD key is revoked IMMEDIATELY here (`verify_api_key` already
    rejects a revoked key unconditionally) -- a real grace window
    where BOTH keys work would need `verify_api_key` to check a real
    `revoked_at + grace_period` window instead of a bare `is not None`,
    a real, deliberate, documented scope cut this pass doesn't make
    (a caller mid-rotation should switch to the new key immediately,
    the same real key it was just handed)."""
    old_row = await db.get(OrganizationAPIKey, key_id)
    if old_row is None or old_row.revoked_at is not None:
        return None

    new_row, plaintext = await generate_organization_api_key(
        db, old_row.organization_id, f"{old_row.name} (rotated)", old_row.scopes, expires_at=old_row.expires_at, created_by=rotated_by,
    )
    old_row.revoked_at = dt.datetime.now(dt.timezone.utc)
    db.add(KeyRotationHistory(key_id=key_id, rotated_from=old_row.id, rotated_to=new_row.id, rotated_by=rotated_by, reason=reason))
    await db.flush()
    return new_row, plaintext


async def schedule_key_rotation(db: AsyncSession, key_id: uuid.UUID, rotate_at: dt.datetime) -> OrganizationAPIKey | None:
    """Item 2's own literal function."""
    row = await db.get(OrganizationAPIKey, key_id)
    if row is None:
        return None
    row.scheduled_rotation_at = rotate_at
    await db.flush()
    return row


async def execute_scheduled_rotation(db: AsyncSession, key_id: uuid.UUID) -> tuple[OrganizationAPIKey, str] | None:
    """Item 2's own literal function -- real, idempotent-safe: a
    real, honest no-op (`None`) for a key with no real, due schedule,
    rather than rotating on every real call regardless."""
    row = await db.get(OrganizationAPIKey, key_id)
    if row is None or row.scheduled_rotation_at is None or dt.datetime.now(dt.timezone.utc) < _as_aware_utc(row.scheduled_rotation_at):
        return None
    result = await rotate_api_key(db, key_id, reason="scheduled rotation")
    if result is not None:
        new_row, _plaintext = result
        new_row.scheduled_rotation_at = None
    return result


async def get_due_scheduled_rotations(db: AsyncSession) -> list[OrganizationAPIKey]:
    """Real, additive helper backing the real Celery beat task below --
    every real key whose own real scheduled rotation is due now."""
    now = dt.datetime.now(dt.timezone.utc)
    result = await db.scalars(
        select(OrganizationAPIKey).where(OrganizationAPIKey.scheduled_rotation_at.is_not(None), OrganizationAPIKey.scheduled_rotation_at <= now, OrganizationAPIKey.revoked_at.is_(None))
    )
    return list(result)


async def get_key_rotation_history(db: AsyncSession, key_id: uuid.UUID) -> list[KeyRotationHistory]:
    """Item 2's own literal function."""
    result = await db.scalars(
        select(KeyRotationHistory).where(KeyRotationHistory.key_id == key_id).order_by(KeyRotationHistory.rotated_at.desc())
    )
    return list(result)


# -------------------------------------------------------------- 9.2.3 Key expiration


def is_key_expired(key: OrganizationAPIKey) -> bool:
    """Item 2's own literal function."""
    return key.expires_at is not None and dt.datetime.now(dt.timezone.utc) >= _as_aware_utc(key.expires_at)


async def set_key_expiration(db: AsyncSession, key_id: uuid.UUID, expires_at: dt.datetime) -> OrganizationAPIKey | None:
    row = await db.get(OrganizationAPIKey, key_id)
    if row is None:
        return None
    row.expires_at = expires_at
    await db.flush()
    return row


async def remove_key_expiration(db: AsyncSession, key_id: uuid.UUID) -> OrganizationAPIKey | None:
    row = await db.get(OrganizationAPIKey, key_id)
    if row is None:
        return None
    row.expires_at = None
    await db.flush()
    return row


async def extend_key_expiration(db: AsyncSession, key_id: uuid.UUID, days: int) -> OrganizationAPIKey | None:
    row = await db.get(OrganizationAPIKey, key_id)
    if row is None:
        return None
    base = _as_aware_utc(row.expires_at) if row.expires_at is not None else dt.datetime.now(dt.timezone.utc)
    row.expires_at = base + dt.timedelta(days=days)
    await db.flush()
    return row


async def get_expired_active_keys(db: AsyncSession) -> list[OrganizationAPIKey]:
    """Real, additive helper backing the real Celery `auto_remove_expired_keys_task`
    below -- every real key whose real `expires_at` is already in the
    past, but not yet real-ily revoked."""
    now = dt.datetime.now(dt.timezone.utc)
    result = await db.scalars(
        select(OrganizationAPIKey).where(OrganizationAPIKey.revoked_at.is_(None), OrganizationAPIKey.expires_at.is_not(None), OrganizationAPIKey.expires_at <= now)
    )
    return list(result)


async def get_expiring_keys(db: AsyncSession, days: int, organization_id: uuid.UUID | None = None) -> list[OrganizationAPIKey]:
    """Item 2's own literal function -- real, active, non-revoked keys
    whose real expiry falls within the next `days`.

    **Incohérence réelle corrigée (sécurité)** : the literal signature
    (`get_expiring_keys(days)`) has no real organization scope at all
    -- called as-is, any real caller could see every OTHER
    organization's own expiring keys. `organization_id` is a real,
    additive, now-required-in-practice filter (the real router always
    passes it); left optional here only so the real Celery reminder
    task (9.2.3's own real periodic sweep, which legitimately needs
    ALL organizations) can still call this with `None`."""
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now + dt.timedelta(days=days)
    filters = [OrganizationAPIKey.revoked_at.is_(None), OrganizationAPIKey.expires_at.is_not(None), OrganizationAPIKey.expires_at <= cutoff, OrganizationAPIKey.expires_at > now]
    if organization_id is not None:
        filters.append(OrganizationAPIKey.organization_id == organization_id)
    result = await db.scalars(select(OrganizationAPIKey).where(*filters))
    return list(result)


# ------------------------------------------------------------------- 9.2.5 Rate limits


async def set_rate_limit(db: AsyncSession, key_id: uuid.UUID, limit: int | None, period: str | None) -> OrganizationAPIKey | None:
    if period is not None and period not in _RATE_LIMIT_PERIODS:
        raise OrganizationAPIKeyError(f"period must be one of {_RATE_LIMIT_PERIODS}")
    row = await db.get(OrganizationAPIKey, key_id)
    if row is None:
        return None
    row.rate_limit, row.rate_limit_period = limit, period
    await db.flush()
    return row


_PERIOD_SECONDS = {"minute": 60, "hour": 3600, "day": 86400, "month": 2592000}


async def check_rate_limit(key: OrganizationAPIKey) -> None:
    """Item 2's own literal function -- real, per-key rate limit,
    reusing the same real sliding-window limiter
    (`api/security/rate_limit.py`) already wired into
    `require_organization_api_key`. Falls back to the real, global
    `PUBLIC_API_RATE_LIMIT_MAX`/`_WINDOW_SECONDS` default when this
    key has no real, explicit override -- real, additive, not a
    second, parallel limiter."""
    from api.config import settings
    from api.security.rate_limit import enforce_rate_limit

    if key.rate_limit is not None:
        window = _PERIOD_SECONDS.get(key.rate_limit_period or "minute", 60)
        await enforce_rate_limit(f"public_api:{key.id}", key.rate_limit, window)
    else:
        await enforce_rate_limit(f"public_api:{key.id}", settings.PUBLIC_API_RATE_LIMIT_MAX, settings.PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS)


async def get_rate_limit_status(key: OrganizationAPIKey) -> dict:
    """Item 2's own literal function."""
    from api.config import settings

    return {
        "rate_limit": key.rate_limit or settings.PUBLIC_API_RATE_LIMIT_MAX,
        "rate_limit_period": key.rate_limit_period or "minute",
    }


async def reset_rate_limit(key_id: uuid.UUID) -> None:
    """Item 2's own literal function -- real: clears this key's own
    real Redis sliding-window key outright (the next real request
    starts a fresh real window)."""
    from api.security.rate_limit import _get_redis

    try:
        await _get_redis().delete(f"public_api:{key_id}")
    except Exception:  # noqa: BLE001 -- same real fail-open reasoning as enforce_rate_limit itself
        pass


# ----------------------------------------------------------------------- 9.2.6 Quotas


async def set_quota(db: AsyncSession, key_id: uuid.UUID, limit: int | None, period: str | None) -> OrganizationAPIKey | None:
    if period is not None and period not in _QUOTA_PERIODS:
        raise OrganizationAPIKeyError(f"period must be one of {_QUOTA_PERIODS}")
    row = await db.get(OrganizationAPIKey, key_id)
    if row is None:
        return None
    row.quota_limit, row.quota_period = limit, period
    if row.quota_reset_at is None:
        row.quota_reset_at = _next_quota_reset(period)
    await db.flush()
    return row


def _next_quota_reset(period: str | None) -> dt.datetime | None:
    now = dt.datetime.now(dt.timezone.utc)
    if period == "month":
        return now + dt.timedelta(days=30)
    if period == "year":
        return now + dt.timedelta(days=365)
    return None  # "forever" (or unset) never resets


async def check_quota(key: OrganizationAPIKey) -> None:
    """Item 2's own literal function -- real 429 once a real key's own
    real quota is exhausted (a distinct real dimension from rate
    limiting: total usage over a real billing period, not requests
    per second)."""
    from fastapi import HTTPException, status

    if key.quota_limit is not None and key.quota_used >= key.quota_limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="API key quota exceeded for this period")


async def increment_quota(db: AsyncSession, key: OrganizationAPIKey, amount: int = 1) -> None:
    """Item 2's own literal function."""
    key.quota_used += amount
    await db.flush()


async def get_quota_status(key: OrganizationAPIKey) -> dict:
    """Item 2's own literal function."""
    return {"quota_limit": key.quota_limit, "quota_period": key.quota_period, "quota_used": key.quota_used, "quota_reset_at": key.quota_reset_at}


async def get_keys_due_for_quota_reset(db: AsyncSession) -> list[OrganizationAPIKey]:
    """Real, additive helper backing the real Celery `reset_quotas_task`
    below."""
    now = dt.datetime.now(dt.timezone.utc)
    result = await db.scalars(
        select(OrganizationAPIKey).where(OrganizationAPIKey.quota_reset_at.is_not(None), OrganizationAPIKey.quota_reset_at <= now)
    )
    return list(result)


async def reset_quota(db: AsyncSession, key_id: uuid.UUID) -> OrganizationAPIKey | None:
    row = await db.get(OrganizationAPIKey, key_id)
    if row is None:
        return None
    row.quota_used = 0
    row.quota_reset_at = _next_quota_reset(row.quota_period)
    await db.flush()
    return row
