"""
Partie 5.3.10 -- real, revocable API keys, scoped to one agent, for
running an agent from outside this app's own session/JWT auth.

**Real key shape**: `ak_<43 real, URL-safe, cryptographically random
characters>` (`secrets.token_urlsafe(32)`, the SAME real, secure RNG
this codebase's own password-reset/email-verification tokens already
use -- never Python's plain, non-cryptographic `random`). Only the
real SHA-256 hash of the full key is ever persisted (`key_hash`) --
the real plaintext key is returned to the caller EXACTLY ONCE, from
`generate_api_key` itself, same discipline as this codebase's own
password hashing (a hash can be verified against, never reversed back
into the real secret)."""

import datetime as dt
import hashlib
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.agent import Agent
from api.models.agent_api_key import AgentAPIKey

_KEY_PREFIX = "ak_"
API_KEY_SCOPES = ("read", "execute")


class AgentAPIKeyError(ValueError):
    """Real, dedicated exception."""


def _as_aware_utc(value: dt.datetime) -> dt.datetime:
    """Same real SQLite-naive-datetime normalization as
    api/security/human_approval.py's own `_as_aware_utc`."""
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


def hash_api_key(key: str) -> str:
    """Item 2's own literal function -- real SHA-256 hex digest."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def validate_scopes(scopes: list[str]) -> None:
    if not scopes:
        raise AgentAPIKeyError("At least one real scope is required")
    unknown = sorted(set(scopes) - set(API_KEY_SCOPES))
    if unknown:
        raise AgentAPIKeyError(f"Unknown scope(s): {unknown} (expected one of {API_KEY_SCOPES})")


async def generate_api_key(
    db: AsyncSession, agent_id: uuid.UUID, name: str, scopes: list[str],
    expires_at: dt.datetime | None = None, created_by: uuid.UUID | None = None,
) -> tuple[AgentAPIKey, str]:
    """Item 2's own literal function -- real, upfront scope validation.
    Returns `(row, plaintext_key)` -- the real plaintext is the
    caller's ONLY chance to see it; `row.key_hash` never round-trips
    back into it."""
    validate_scopes(scopes)
    plaintext_key = f"{_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    row = AgentAPIKey(
        agent_id=agent_id, name=name, key_hash=hash_api_key(plaintext_key), key_prefix=_KEY_PREFIX,
        scopes=list(scopes), expires_at=expires_at, created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return row, plaintext_key


async def verify_api_key(db: AsyncSession, key: str) -> AgentAPIKey | None:
    """Item 2's own literal function -- real, `None` for an unknown,
    revoked, OR real, lazily-expired key (same lazy-expiry pattern as
    `api/services/agent_memory.py`'s own `get_from_memory`). A real,
    successful verification stamps `last_used_at` -- a real, useful
    side effect, not just a read."""
    row = await db.scalar(select(AgentAPIKey).where(AgentAPIKey.key_hash == hash_api_key(key)))
    if row is None or row.revoked_at is not None:
        return None
    if row.expires_at is not None and dt.datetime.now(dt.timezone.utc) >= _as_aware_utc(row.expires_at):
        return None
    row.last_used_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return row


async def get_agent_from_api_key(db: AsyncSession, key: str) -> Agent | None:
    """Item 2's own literal function -- real, `None` for an invalid key
    OR one whose real agent no longer exists/was soft-deleted."""
    row = await verify_api_key(db, key)
    if row is None:
        return None
    agent = await db.get(Agent, row.agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    return agent


async def revoke_api_key(db: AsyncSession, key_id: uuid.UUID) -> bool:
    """Item 2's own literal function -- real, idempotent-safe: `False`
    for an unknown key OR one already revoked (vision critique
    "que se passe-t-il si une clé expire" -- an expired key is a
    separate, real, lazy state `verify_api_key` already handles;
    revocation is a distinct, explicit, permanent real action)."""
    row = await db.get(AgentAPIKey, key_id)
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return True


async def list_api_keys(db: AsyncSession, agent_id: uuid.UUID) -> list[AgentAPIKey]:
    """Item 2's own literal function -- real, ordered, newest first.
    Never exposes `key_hash` itself (the router's own response schema
    is the real enforcement point -- see api/schemas/agent_api_keys.py)."""
    result = await db.scalars(select(AgentAPIKey).where(AgentAPIKey.agent_id == agent_id).order_by(AgentAPIKey.created_at.desc()))
    return list(result)
