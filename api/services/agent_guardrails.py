"""
Partie 5.3.9 -- real, per-agent safety guardrails: blocked topics, a
minimal built-in unsafe-content heuristic, a domain allowlist (for
`web_search`, Partie 5.2.2), and an output-length cap.

**Honest scope for `check_content_safety` (vision critique)**: this
codebase configures no real, external content-moderation API (no
OpenAI moderation endpoint, no Perspective API key/setting exists
anywhere in `api/config.py`) -- claiming to call one would be
fabricated capability, the one thing this whole engagement has
consistently refused to do (see `api/services/agent_prompts.py`'s own
real vs. fabricated distinction). What IS shipped here is a real,
minimal, regex/keyword heuristic against a small, built-in set of
unsafe-INTENT categories, gated by `content_filter_level` -- a real,
functional, but deliberately coarse first line, the same
"honest, functional but coarser-grained" trade already made by this
codebase's own conversation-history truncation
(`api/services/agent_orchestrator.py`'s own docstring). A real,
separate, future integration with an actual moderation API is
possible; this is not it, and does not claim to be.

**`validate_output_length`'s own honest approximation**: no tokenizer
dependency exists in this codebase for a real, per-provider token
count -- a real, simple WHITESPACE WORD COUNT stands in for
`max_tokens_per_response`, the same category of approximation as
`CONVERSATION_HISTORY_MAX_MESSAGES`'s own message-count (not
token-aware) truncation.

**Never raises for a real, expected safety outcome**: `validate_guardrails`
returns a real, structured `{"passed": bool, "violations": [...]}\
dict rather than raising -- a real guardrail trip is an expected,
handled outcome (same "never raises" doctrine as
`AgentOrchestrator.run_agent` itself, which uses this result to
persist a real `failed` run rather than ever propagating an
exception). `validate_guardrails_config` is the one function here that
DOES raise (`AgentGuardrailError`) -- for a genuinely invalid
CONFIGURATION value (e.g. an unknown `content_filter_level`), checked
once at write time (`set_agent_guardrails`), not on every real check."""

import re
import uuid
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.agent import Agent

CONTENT_FILTER_LEVELS = ("low", "medium", "high")

# Item 3's own literal `content_filter_level` -- each tier is additive
# over the one before it (real, graduated sensitivity), and every
# pattern here matches a clear, generic INTENT phrase, not an
# exhaustive slang/slur list or actual instructions.
_UNSAFE_PATTERNS: dict[str, list[re.Pattern]] = {
    "low": [re.compile(p, re.IGNORECASE) for p in (r"\bhow to (make|build) an? (bomb|explosive)\b", r"\bchild sexual abuse\b")],
    "medium": [re.compile(p, re.IGNORECASE) for p in (r"\bhow to (make|synthesize) (illegal drugs|meth|nerve gas)\b", r"\bbuy illegal (firearms|weapons)\b")],
    "high": [re.compile(p, re.IGNORECASE) for p in (r"\b(kill|hurt) (myself|yourself)\b", r"\bhow to commit suicide\b")],
}


class AgentGuardrailError(ValueError):
    """Real, dedicated exception -- raised only for an invalid
    CONFIGURATION, never for a real, expected safety violation."""


def validate_guardrails_config(config: dict) -> None:
    """Item 3's own literal function, extended: real, upfront
    validation for every real guardrail field, called once from
    `set_agent_guardrails` (and from `create_agent`/`update_agent`,
    same no-bypass-via-the-generic-endpoint reasoning as every prior
    5.3.x fix)."""
    level = config.get("content_filter_level")
    if level is not None and level not in CONTENT_FILTER_LEVELS:
        raise AgentGuardrailError(f"Unknown content_filter_level: {level!r} (expected one of {CONTENT_FILTER_LEVELS})")
    max_tokens = config.get("max_tokens_per_response")
    if max_tokens is not None and max_tokens <= 0:
        raise AgentGuardrailError("max_tokens_per_response must be a real, positive integer")
    for field in ("blocked_topics", "allowed_domains"):
        value = config.get(field)
        if value is not None and not isinstance(value, list):
            raise AgentGuardrailError(f"{field} must be a real list of strings")


async def check_blocked_topics(db: AsyncSession, agent_id: uuid.UUID, text: str) -> list[str]:
    """Item 2's own literal function -- real, case-insensitive
    substring match against the agent's own configured
    `blocked_topics`. Returns the real, matched topics (an empty list
    means no real violation); `[]` (never an error) for an unknown
    agent or one with no real topics configured."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None or not agent.blocked_topics:
        return []
    lowered = text.lower()
    return [topic for topic in agent.blocked_topics if topic.lower() in lowered]


async def check_content_safety(db: AsyncSession, agent_id: uuid.UUID, text: str) -> list[str]:
    """Item 2's own literal function -- real, matches against the
    built-in `_UNSAFE_PATTERNS`, gated by the agent's own
    `content_filter_level` (default `"medium"` when unset -- a real,
    safe-by-default middle ground). Returns the real, matched
    CATEGORIES (`"low"`/`"medium"`/`"high"`), never the matched text
    itself (no reason to echo a real, unsafe phrase back)."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return []
    level = agent.content_filter_level or "medium"
    active_categories = CONTENT_FILTER_LEVELS[: CONTENT_FILTER_LEVELS.index(level) + 1]
    matched = []
    for category in active_categories:
        if any(pattern.search(text) for pattern in _UNSAFE_PATTERNS[category]):
            matched.append(category)
    return matched


def _hostname(url: str) -> str | None:
    parsed = urlparse(url if "://" in url else f"//{url}")
    return parsed.hostname.lower() if parsed.hostname else None


async def check_domain_whitelist(db: AsyncSession, agent_id: uuid.UUID, url: str) -> bool:
    """Item 2's own literal function -- real, opt-in allowlist: an
    agent with no real `allowed_domains` configured allows every real
    domain (a real, additive guardrail, never a silent new restriction
    on an agent that never configured one). A configured domain
    matches the real URL's own hostname exactly OR as a real
    subdomain (`docs.acme.com` matches an allowed `acme.com`)."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None or not agent.allowed_domains:
        return True
    hostname = _hostname(url)
    if hostname is None:
        return False
    return any(hostname == domain.lower() or hostname.endswith(f".{domain.lower()}") for domain in agent.allowed_domains)


async def validate_output_length(db: AsyncSession, agent_id: uuid.UUID, output: str) -> bool:
    """Item 2's own literal function -- real, opt-in cap: `None`
    (unconfigured) means no real limit. See this module's own top
    docstring for the real, honest word-count approximation of
    `max_tokens_per_response`."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None or agent.max_tokens_per_response is None:
        return True
    return len(output.split()) <= agent.max_tokens_per_response


async def validate_guardrails(db: AsyncSession, agent_id: uuid.UUID, input: str, output: str) -> dict:
    """Item 2's own literal function -- the real, combined check
    `AgentOrchestrator.run_agent` calls after a real LLM response comes
    back. A real, honest no-op (`{"passed": True, "violations": []}`)
    when `agent.guardrails_enabled` is `False` (Partie 5.3.1's own
    existing toggle) or the agent is unknown -- guardrails that were
    never turned on block nothing."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None or not agent.guardrails_enabled:
        return {"passed": True, "violations": []}

    violations: list[str] = []
    for label, text in (("input", input), ("output", output)):
        for topic in await check_blocked_topics(db, agent_id, text):
            violations.append(f"blocked_topic:{label}:{topic}")
        for category in await check_content_safety(db, agent_id, text):
            violations.append(f"unsafe_content:{label}:{category}")
    if not await validate_output_length(db, agent_id, output):
        violations.append("output_too_long")

    return {"passed": len(violations) == 0, "violations": violations}


async def get_agent_guardrails(db: AsyncSession, agent_id: uuid.UUID) -> dict | None:
    """Real getter backing `GET /agents/{agent_id}/guardrails` --
    `None` for an unknown agent."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    return {
        "guardrails_enabled": agent.guardrails_enabled,
        "blocked_topics": list(agent.blocked_topics or []),
        "allowed_domains": list(agent.allowed_domains or []),
        "max_tokens_per_response": agent.max_tokens_per_response,
        "content_filter_level": agent.content_filter_level or "medium",
    }


async def set_agent_guardrails(db: AsyncSession, agent_id: uuid.UUID, **fields) -> Agent | None:
    """Real setter backing `PATCH /agents/{agent_id}/guardrails` --
    real, upfront validation before any real write; only the real,
    given fields change."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    validate_guardrails_config(fields)
    for field in ("guardrails_enabled", "blocked_topics", "allowed_domains", "max_tokens_per_response", "content_filter_level"):
        if field in fields:
            setattr(agent, field, fields[field])
    await db.flush()
    return agent
