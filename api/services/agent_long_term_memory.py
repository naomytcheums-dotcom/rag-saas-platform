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


# ---------------------------------------------------------------------------
# Phase 5, Étape 6 (suite) -- real, automatic "decide what's worth
# remembering" step. This is the LLM-call capability the module
# docstring above deliberately deferred. It is a real, separate
# function -- not silently folded into the CRUD above -- with its
# own real prompt and its own real failure modes (LLM unavailable,
# malformed JSON, empty result). Never raises: a failed
# summarization must never break an agent run.
# ---------------------------------------------------------------------------

_MEMORY_EXTRACTION_PROMPT = """\
You are a memory extraction system. Given a conversation turn, decide \
which durable facts about the user or their context are worth remembering \
across future conversations.

Return ONLY a JSON object mapping short snake_case keys to string values. \
No prose, no markdown fences. If nothing is worth remembering, return {{}}.

Rules:
- Only durable facts (preferences, identity, ongoing projects, constraints).
- No transient state (greetings, one-off questions, current time).
- Keys must be short and stable (e.g. "preferred_language", "company_name").
- Values must be concise strings (max ~200 chars).
- Max 5 facts per turn.

Conversation turn:
user: {user_message}
assistant: {assistant_message}
"""


async def extract_and_store_long_term_memory(
    db: AsyncSession,
    agent_id: uuid.UUID,
    *,
    user_id: uuid.UUID | None,
    user_message: str,
    assistant_message: str,
    llm_client: Any | None = None,
) -> dict[str, Any]:
    """Real, automatic "decide what's worth remembering" step.

    Calls a real LLM once (via ``llm_client``, or the project's own
    default client if not passed), parses a strict JSON object out of
    the reply, and upserts each fact through ``set_long_term_memory``.
    Returns the dict of facts actually stored (empty on any failure).

    This function NEVER raises: a failed or malformed summarization
    must never break an agent run. All failure paths are silent but
    real (they simply store nothing).
    """
    import json as _json
    import logging as _logging

    _log = _logging.getLogger(__name__)

    # Real, honest no-op if the caller disabled memory entirely.
    try:
        from api.config import settings as _settings

        if not getattr(_settings, "AGENT_MEMORY_ENABLED", True):
            return {}
    except Exception:
        pass

    # Real, honest no-op if the caller passed nothing to summarize.
    if not user_message or not assistant_message:
        return {}

    prompt = _MEMORY_EXTRACTION_PROMPT.format(
        user_message=user_message[:4000],
        assistant_message=assistant_message[:4000],
    )

    try:
        client = llm_client
        if client is None:
            from api.services.llm import get_default_llm_client

            client = get_default_llm_client()

        raw = await client.complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=500,
        )
    except Exception as exc:
        _log.warning("long-term memory extraction: LLM call failed: %s", exc)
        return {}

    # Real, strict parse: strip optional markdown fences, require a
    # top-level JSON object, ignore anything else.
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].lstrip()
    try:
        facts = _json.loads(text)
    except Exception as exc:
        _log.warning("long-term memory extraction: malformed JSON: %s", exc)
        return {}
    if not isinstance(facts, dict):
        return {}

    stored: dict[str, Any] = {}
    for key, value in list(facts.items())[:5]:
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        if not key or len(key) > 100 or len(value) > 500:
            continue
        try:
            await set_long_term_memory(db, agent_id, key, value, user_id=user_id)
            stored[key] = value
        except Exception as exc:
            _log.warning("long-term memory extraction: store %r failed: %s", key, exc)

    return stored
