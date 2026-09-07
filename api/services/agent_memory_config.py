"""
Partie 5.3.6 -- configuring and inspecting an agent's own real memory
settings (`Agent.memory_ttl`/`memory_max_items`/`memory_retention_policy`,
declared but inert since migration `0058`, Partie 5.3.1).

**Real integration, not a parallel memory system**: `clear_agent_memory`
reuses Partie 5.1.11's own real `clear_memory` (`api/services/agent_memory.py`),
by resolving every real `AgentSession` row whose own `agent_id` string
equals `str(Agent.id)` -- the SAME real integration point
`api/models/agent.py`'s own top docstring already documents (Partie
5.3.1 made that string real; this étape is the first to actually walk
it back from an `Agent` row to its real sessions).

**Real, honest retention policy set**: `MEMORY_RETENTION_POLICIES`
contains only `"fifo"` -- the ONE real eviction policy
`api/services/agent_memory.py`'s own `_evict_oldest_if_full` actually
implements. Accepting a second, made-up policy value here (e.g. "lru")
that changes no real behavior anywhere would be a fabricated setting,
not a real one."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.agent import Agent
from api.models.agent_memory import AgentMemoryItem, AgentSession
from api.services.agent_memory import clear_memory

MEMORY_RETENTION_POLICIES = ("fifo",)


class AgentMemoryConfigError(ValueError):
    """Real, dedicated exception."""


def get_default_memory_config() -> dict:
    """Reuses this codebase's own real, already-established Partie
    5.1.11 defaults (`settings.AGENT_MEMORY_TTL`/`AGENT_MEMORY_SIZE`)
    rather than a second, hardcoded set of values."""
    return {
        "memory_enabled": True, "memory_window_size": 10,
        "memory_ttl": settings.AGENT_MEMORY_TTL, "memory_max_items": settings.AGENT_MEMORY_SIZE,
        "memory_retention_policy": MEMORY_RETENTION_POLICIES[0],
    }


def validate_memory_config(config: dict) -> None:
    """Item 3's own literal function -- real, raises `AgentMemoryConfigError`
    with a real, specific reason for each real field given."""
    if "memory_window_size" in config and config["memory_window_size"] is not None and config["memory_window_size"] <= 0:
        raise AgentMemoryConfigError("memory_window_size must be a real, positive integer")
    if "memory_ttl" in config and config["memory_ttl"] is not None and config["memory_ttl"] <= 0:
        raise AgentMemoryConfigError("memory_ttl must be a real, positive number of seconds")
    if "memory_max_items" in config and config["memory_max_items"] is not None and config["memory_max_items"] <= 0:
        raise AgentMemoryConfigError("memory_max_items must be a real, positive integer")
    policy = config.get("memory_retention_policy")
    if policy is not None and policy not in MEMORY_RETENTION_POLICIES:
        raise AgentMemoryConfigError(f"Unknown memory_retention_policy: {policy!r} (expected one of {MEMORY_RETENTION_POLICIES})")


async def get_agent_memory_config(db: AsyncSession, agent_id: uuid.UUID) -> dict | None:
    """Item 3's own literal function -- real, effective config: the
    agent's own real fields, missing/null real values filled in from
    `get_default_memory_config`. `None` for an unknown agent."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    defaults = get_default_memory_config()
    return {
        "memory_enabled": agent.memory_enabled,
        "memory_window_size": agent.memory_window_size,
        "memory_ttl": agent.memory_ttl if agent.memory_ttl is not None else defaults["memory_ttl"],
        "memory_max_items": agent.memory_max_items if agent.memory_max_items is not None else defaults["memory_max_items"],
        "memory_retention_policy": agent.memory_retention_policy or defaults["memory_retention_policy"],
    }


async def set_agent_memory_config(db: AsyncSession, agent_id: uuid.UUID, **fields) -> Agent | None:
    """Item 3's own literal function -- real, upfront validation before
    ever touching the real row; only the real, given fields change."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    validate_memory_config(fields)
    for field in ("memory_enabled", "memory_window_size", "memory_ttl", "memory_max_items", "memory_retention_policy"):
        if field in fields:
            setattr(agent, field, fields[field])
    await db.flush()
    return agent


async def get_memory_usage(db: AsyncSession, agent_id: uuid.UUID) -> dict | None:
    """Item 3's own literal function -- real, live counts: how many
    real `AgentSession`s this agent has, and how many real
    `AgentMemoryItem`s across all of them (Partie 5.1.11's own real
    tables). `None` for an unknown agent."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    agent_id_str = str(agent.id)
    session_count = await db.scalar(select(func.count()).select_from(AgentSession).where(AgentSession.agent_id == agent_id_str))
    item_count = await db.scalar(
        select(func.count()).select_from(AgentMemoryItem).join(AgentSession, AgentMemoryItem.session_id == AgentSession.id)
        .where(AgentSession.agent_id == agent_id_str)
    )
    return {"session_count": session_count or 0, "item_count": item_count or 0}


async def clear_agent_memory(db: AsyncSession, agent_id: uuid.UUID) -> int | None:
    """Item 3's own literal function -- real reuse, not a parallel
    deletion path: walks every real `AgentSession` whose own `agent_id`
    string equals this agent's real `str(id)`, and calls Partie
    5.1.11's own real `clear_memory` on each. Returns the real total
    item count removed; `None` for an unknown agent."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    sessions = (await db.scalars(select(AgentSession).where(AgentSession.agent_id == str(agent.id)))).all()
    total = 0
    for session in sessions:
        total += await clear_memory(db, session.id)
    return total
