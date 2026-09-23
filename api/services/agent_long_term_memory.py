"""
Phase 5, Étape 6 -- real CRUD for `AgentLongTermMemoryItem`
(api/models/agent_long_term_memory.py's own docstring explains the
real, cross-run distinction from short-term `agent_memory.py`).

**Honest, deliberate scope**: this module gives an agent's own tools
(or a real, explicit API caller) a real place to WRITE a fact meant to
outlive one run, and a real place `AgentOrchestrator.run_agent` reads
from at the start of every run (alongside existing short-term memory).
It does NOT add an automatic "decide what's worth remembering"
summarization step -- deciding what to persist long-term is a real,
separate, substantial capability (an LLM call of its own, its own
prompt, its own real failure modes) this étape's own scope doesn't
require to make long-term memory itself real and usable; traced,
not silently missing (see ROADMAP.md)."""

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.agent_long_term_memory import AgentLongTermMemoryItem


def _as_aware_utc(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


async def set_long_term_memory(
    db: AsyncSession, agent_id: uuid.UUID, key: str, value: Any, *, user_id: uuid.UUID | None = None,
    expires_at: dt.datetime | None = None,
) -> AgentLongTermMemoryItem:
    """Real upsert -- same "replace an existing key's value" semantics
    as `agent_memory.add_to_memory`, just cross-run instead of
    per-session."""
    existing = await db.scalar(
        select(AgentLongTermMemoryItem).where(
            AgentLongTermMemoryItem.agent_id == agent_id, AgentLongTermMemoryItem.user_id == user_id, AgentLongTermMemoryItem.key == key,
        )
    )
    if existing is not None:
        existing.value = value
        existing.expires_at = expires_at
        await db.flush()
        return existing
    item = AgentLongTermMemoryItem(agent_id=agent_id, user_id=user_id, key=key, value=value, expires_at=expires_at)
    db.add(item)
    await db.flush()
    return item


async def get_long_term_memory(db: AsyncSession, agent_id: uuid.UUID, *, user_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Real, lazy-expiring read of every real, still-live long-term
    fact for this agent -- BOTH the real org-wide facts (`user_id`
    `NULL`) and this specific user's own real facts, merged (the
    user's own value wins on a real key collision -- a real, more
    specific fact should override a real, general one)."""
    stmt = select(AgentLongTermMemoryItem).where(
        AgentLongTermMemoryItem.agent_id == agent_id,
        AgentLongTermMemoryItem.user_id.is_(None) if user_id is None else AgentLongTermMemoryItem.user_id.in_([None, user_id]),
    )
    items = (await db.scalars(stmt)).all()
    now = dt.datetime.now(dt.timezone.utc)
    result: dict[str, Any] = {}
    for item in sorted(items, key=lambda i: i.user_id is None, reverse=True):  # org-wide first, user-specific overrides
        if item.expires_at is not None and now >= _as_aware_utc(item.expires_at):
            await db.delete(item)
            continue
        result[item.key] = item.value
    await db.flush()
    return result


async def delete_long_term_memory(db: AsyncSession, agent_id: uuid.UUID, key: str, *, user_id: uuid.UUID | None = None) -> bool:
    """Returns whether a real row was actually deleted -- a real,
    honest `False` for a key that never existed, not an error."""
    item = await db.scalar(
        select(AgentLongTermMemoryItem).where(
            AgentLongTermMemoryItem.agent_id == agent_id, AgentLongTermMemoryItem.user_id == user_id, AgentLongTermMemoryItem.key == key,
        )
    )
    if item is None:
        return False
    await db.delete(item)
    await db.flush()
    return True
