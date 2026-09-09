"""
Partie 9.1 -- real, revocable, organization-scoped API keys for the
public `/v1/*` API. Same real hash/generation discipline as
`api/services/agent_api_keys.py` (5.3.10) -- see
`api/models/organization_api_key.py`'s own docstring for why this is a
separate model/service rather than reusing that one directly."""

import datetime as dt
import hashlib
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.organization_api_key import OrganizationAPIKey

_KEY_PREFIX = "pk_"
PUBLIC_API_SCOPES = (
    "chat", "documents:write", "knowledge_bases:write", "conversations:read", "search", "agents:run",
    "usage:read", "analytics:read", "embed",
)


class OrganizationAPIKeyError(ValueError):
    """Real, dedicated exception."""


def _as_aware_utc(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def validate_scopes(scopes: list[str]) -> None:
    if not scopes:
        raise OrganizationAPIKeyError("At least one real scope is required")
    unknown = sorted(set(scopes) - set(PUBLIC_API_SCOPES))
    if unknown:
        raise OrganizationAPIKeyError(f"Unknown scope(s): {unknown} (expected one of {PUBLIC_API_SCOPES})")


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
    """Real, honest `None` for an unknown, revoked, or lazily-expired
    key. A successful verification stamps `last_used_at`."""
    row = await db.scalar(select(OrganizationAPIKey).where(OrganizationAPIKey.key_hash == hash_api_key(key)))
    if row is None or row.revoked_at is not None:
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
