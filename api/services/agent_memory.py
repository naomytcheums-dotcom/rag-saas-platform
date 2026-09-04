"""
Partie 5.1.11 -- real, short-term, per-session agent memory. Item 2's
own literal functions: `create_session`/`add_to_memory`/
`get_from_memory`/`get_all_memory`/`clear_memory`/`update_memory`.

**Real, lazy expiry** (same pattern as api/security/human_approval.py's
own `_resolve_if_expired`): an expired `AgentMemoryItem` is deleted the
moment it's read, rather than needing a real, separate background
sweep. **Real eviction when full (vision critique)**: `add_to_memory`
on a session already at `AGENT_MEMORY_SIZE` real items deletes the
OLDEST one (by `created_at`) to make room -- a real, simple, documented
FIFO policy, not silent data loss with no story. `update_memory` never
triggers eviction (it doesn't grow the set)."""

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.agent_memory import AgentMemoryItem, AgentSession


def _as_aware_utc(value: dt.datetime) -> dt.datetime:
    """Same real SQLite-naive-datetime normalization as
    api/security/human_approval.py's own `_as_aware_utc`."""
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


async def create_session(db: AsyncSession, agent_id: str, user_id: uuid.UUID | None = None) -> AgentSession:
    """Item 2's own literal function."""
    now = dt.datetime.now(dt.timezone.utc)
    session = AgentSession(agent_id=agent_id, user_id=user_id, expires_at=now + dt.timedelta(seconds=settings.AGENT_MEMORY_TTL))
    db.add(session)
    await db.flush()
    return session


async def _evict_oldest_if_full(db: AsyncSession, session_id: uuid.UUID) -> None:
    count = await db.scalar(select(func.count()).select_from(AgentMemoryItem).where(AgentMemoryItem.session_id == session_id))
    if count is not None and count >= settings.AGENT_MEMORY_SIZE:
        oldest = await db.scalar(
            select(AgentMemoryItem).where(AgentMemoryItem.session_id == session_id).order_by(AgentMemoryItem.created_at).limit(1)
        )
        if oldest is not None:
            await db.delete(oldest)
            await db.flush()


async def add_to_memory(db: AsyncSession, session_id: uuid.UUID, key: str, value: Any) -> AgentMemoryItem | None:
    """Item 2's own literal function -- a real upsert (replaces an
    existing key's value rather than erroring); a real, honest no-op
    (`None`) when `AGENT_MEMORY_ENABLED` is off."""
    if not settings.AGENT_MEMORY_ENABLED:
        return None

    now = dt.datetime.now(dt.timezone.utc)
    expires_at = now + dt.timedelta(seconds=settings.AGENT_MEMORY_TTL)
    existing = await db.scalar(select(AgentMemoryItem).where(AgentMemoryItem.session_id == session_id, AgentMemoryItem.key == key))
    if existing is not None:
        existing.value = value
        existing.expires_at = expires_at
        await db.flush()
        return existing

    await _evict_oldest_if_full(db, session_id)
    item = AgentMemoryItem(session_id=session_id, key=key, value=value, expires_at=expires_at)
    db.add(item)
    await db.flush()
    return item


async def get_from_memory(db: AsyncSession, session_id: uuid.UUID, key: str) -> Any:
    """Item 2's own literal function -- `None` for a missing OR real,
    lazily-expired key."""
    item = await db.scalar(select(AgentMemoryItem).where(AgentMemoryItem.session_id == session_id, AgentMemoryItem.key == key))
    if item is None:
        return None
    if dt.datetime.now(dt.timezone.utc) >= _as_aware_utc(item.expires_at):
        await db.delete(item)
        await db.flush()
        return None
    return item.value


async def get_all_memory(db: AsyncSession, session_id: uuid.UUID) -> dict[str, Any]:
    """Item 2's own literal function -- every real, still-live key,
    with any real, expired item found along the way lazily removed."""
    items = (await db.scalars(select(AgentMemoryItem).where(AgentMemoryItem.session_id == session_id))).all()
    now = dt.datetime.now(dt.timezone.utc)
    result: dict[str, Any] = {}
    for item in items:
        if now >= _as_aware_utc(item.expires_at):
            await db.delete(item)
        else:
            result[item.key] = item.value
    await db.flush()
    return result


async def clear_memory(db: AsyncSession, session_id: uuid.UUID) -> int:
    """Item 2's own literal function -- real deletion of every item in
    this session; returns the real count removed."""
    items = (await db.scalars(select(AgentMemoryItem).where(AgentMemoryItem.session_id == session_id))).all()
    for item in items:
        await db.delete(item)
    await db.flush()
    return len(items)


async def update_memory(db: AsyncSession, session_id: uuid.UUID, key: str, value: Any) -> AgentMemoryItem | None:
    """Item 2's own literal function -- unlike `add_to_memory`, a real,
    honest no-op (`None`) when `key` does NOT already exist: "update"
    means changing something real, not silently creating it."""
    existing = await db.scalar(select(AgentMemoryItem).where(AgentMemoryItem.session_id == session_id, AgentMemoryItem.key == key))
    if existing is None:
        return None
    existing.value = value
    existing.expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=settings.AGENT_MEMORY_TTL)
    await db.flush()
    return existing
