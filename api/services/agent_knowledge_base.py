"""
Partie 5.3.4 -- selecting and validating an agent's own real knowledge
base.

**Real reuse, not a second entity**: `api/models/agent.py`'s own
`knowledge_base_id` already references the SAME real `workspaces`
table `Document.workspace_id` uses (Partie 1.2.4/2.x) -- this codebase
has no dedicated `KnowledgeBase` table, a `Workspace` already IS the
real document container. `get_available_knowledge_bases` below simply
lists real workspaces, it does not introduce a parallel concept.

**Real, cross-organization validation this étape adds** -- neither
`create_agent` nor `update_agent` (Partie 5.3.1,
`api/security/agents.py`) previously checked that a given
`knowledge_base_id` actually belongs to the SAME organization as the
agent itself; nothing stopped a manager from pointing an agent at
another organization's real workspace (its `id` is a real, guessable
UUID once known, e.g. leaked in a URL). `validate_knowledge_base_access`
closes that real gap, and is now called from both functions (see
`api/security/agents.py`)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.agent import Agent
from api.models.workspace import Workspace
from api.security.organization_settings import DEFAULT_SETTINGS


class AgentKnowledgeBaseError(ValueError):
    """Real, dedicated exception."""


def get_default_kb_config() -> dict:
    """Reuses this codebase's own real, already-established retrieval
    defaults (Partie 3.3.6/3.3.7's own `DEFAULT_SETTINGS`), not a
    second, competing set of hardcoded values."""
    return {"top_k": DEFAULT_SETTINGS["top_k"], "score_threshold": DEFAULT_SETTINGS["score_threshold"]}


async def validate_knowledge_base_access(db: AsyncSession, organization_id: uuid.UUID, workspace_id: uuid.UUID) -> Workspace:
    """Item 2's own literal function -- real, raises `AgentKnowledgeBaseError`
    with a real, specific reason when the workspace doesn't exist, or
    exists but belongs to a different, real organization (never reveals
    which via the error message, same anti-enumeration posture as
    `api/security/agents.py`'s own 404s)."""
    workspace = await db.get(Workspace, workspace_id)
    if workspace is None or workspace.organization_id != organization_id:
        raise AgentKnowledgeBaseError(f"Knowledge base {workspace_id} was not found in this organization")
    return workspace


async def get_agent_knowledge_base(db: AsyncSession, agent_id: uuid.UUID) -> uuid.UUID | None:
    """Item 2's own literal function -- the agent's own real
    `knowledge_base_id`, `None` for an unknown/soft-deleted agent or an
    agent with none configured."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    return agent.knowledge_base_id


async def set_agent_knowledge_base(
    db: AsyncSession, agent_id: uuid.UUID, knowledge_base_id: uuid.UUID | None, config: dict | None = None,
) -> Agent | None:
    """Item 2's own literal function -- real, upfront cross-organization
    validation before ever touching the real row. `knowledge_base_id=None`
    is a real, valid way to unset an agent's KB (search falls back to
    `workspace_id`'s own documents, per `api/services/retrieval_pipeline.py`)."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None

    if knowledge_base_id is not None:
        await validate_knowledge_base_access(db, agent.organization_id, knowledge_base_id)
    agent.knowledge_base_id = knowledge_base_id

    if config is not None:
        agent.knowledge_base_config = {**get_default_kb_config(), **(agent.knowledge_base_config or {}), **config}

    await db.flush()
    return agent


async def get_agent_kb_config(db: AsyncSession, agent_id: uuid.UUID) -> dict | None:
    """Item 2's own literal function -- real, effective config: the
    real agent's own `knowledge_base_config`, missing real keys filled
    in from `get_default_kb_config`. `None` for an unknown agent."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    return {**get_default_kb_config(), **(agent.knowledge_base_config or {})}


async def get_available_knowledge_bases(db: AsyncSession, organization_id: uuid.UUID) -> list[Workspace]:
    """Item 2's own literal function -- every real workspace in the
    agent's own organization is a real, selectable knowledge base
    (same query shape as `api/routers/workspaces.py`'s own
    `list_workspaces`, Partie 1.2.4)."""
    result = await db.scalars(
        select(Workspace).where(Workspace.organization_id == organization_id).order_by(Workspace.created_at)
    )
    return list(result)


# -- Hardening Mission (§11/§14, ChangeLab + Factory) ---------------------------
#
# A real, confirmed gap: `Agent.knowledge_base_config` was written by the
# MCP tools `create_rag_agent`/`update_retrieval_config` (and by
# `set_agent_knowledge_base` above) but READ BY NOTHING that ever ran a
# query -- neither `agent_orchestrator` nor the Eval Lab consulted it, so a
# ChangeLab change (e.g. top_k 5 -> 10) could never move a benchmark
# metric: a decorative knob. `run_evaluation` now applies it for real
# (see api/services/evaluation_results.py), via the two pure helpers below.

RETRIEVAL_STRATEGY_ALIASES = {"vector": "vector_only", "bm25": "bm25_only"}
KNOWN_RETRIEVAL_STRATEGIES = ("hybrid", "vector_only", "bm25_only", "hybrid_reranked", "semantic")
# Keys that map onto a real `search_with_context` keyword argument ...
_SEARCH_KWARG_KEYS = ("top_k", "score_threshold", "strategy", "reranker")
# ... and keys that map onto a real organization-settings flag read inside search().
_SETTINGS_FLAG_KEYS = {"hyde": "hyde_enabled", "mmr": "mmr_enabled", "multi_query": "multi_query_enabled"}
_RECOGNIZED_KB_CONFIG_KEYS = set(_SEARCH_KWARG_KEYS) | set(_SETTINGS_FLAG_KEYS) | {"retrieval_strategy"}


def validate_retrieval_config(config: dict) -> dict:
    """Real, strict validation + normalization of a retrieval config
    coming from an external caller (the MCP tools): unknown keys are
    REJECTED rather than silently stored (a typo like `topk` must fail
    loudly, never produce an inert, "successful" change), values are
    bounds-checked, and `AGENTS.md`'s own documented short strategy names
    (`vector`/`bm25`) are mapped onto the real ones."""
    from api.config import settings

    if not isinstance(config, dict):
        raise AgentKnowledgeBaseError("retrieval_config must be an object")
    unknown = sorted(set(config) - _RECOGNIZED_KB_CONFIG_KEYS)
    if unknown:
        raise AgentKnowledgeBaseError(f"Unknown retrieval_config key(s): {unknown} (expected a subset of {sorted(_RECOGNIZED_KB_CONFIG_KEYS)})")

    out = dict(config)
    if "retrieval_strategy" in out:
        out.setdefault("strategy", out.pop("retrieval_strategy"))
    if "strategy" in out:
        strategy = RETRIEVAL_STRATEGY_ALIASES.get(out["strategy"], out["strategy"])
        if strategy not in KNOWN_RETRIEVAL_STRATEGIES:
            raise AgentKnowledgeBaseError(f"Unknown strategy {out['strategy']!r} (expected one of {KNOWN_RETRIEVAL_STRATEGIES})")
        out["strategy"] = strategy
    if "top_k" in out:
        top_k = out["top_k"]
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= settings.TOP_K_MAX:
            raise AgentKnowledgeBaseError(f"top_k must be an integer between 1 and {settings.TOP_K_MAX}")
    if "score_threshold" in out:
        threshold = out["score_threshold"]
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0.0 <= threshold <= 1.0:
            raise AgentKnowledgeBaseError("score_threshold must be a number between 0 and 1")
    if "reranker" in out:
        if out["reranker"] in (None, "none"):
            out.pop("reranker")
        elif not isinstance(out["reranker"], str) or not out["reranker"].strip():
            raise AgentKnowledgeBaseError("reranker must be a non-empty model name, or 'none'")
    for flag in _SETTINGS_FLAG_KEYS:
        if flag in out and not isinstance(out[flag], bool):
            raise AgentKnowledgeBaseError(f"{flag} must be a boolean")
    return out


def retrieval_overrides_from_kb_config(config: dict | None) -> tuple[dict, dict]:
    """Pure: split a stored agent `knowledge_base_config` into
    `(search_kwargs, org_settings_overrides)`. Only keys physically
    present AND well-formed are applied -- a malformed legacy value is
    skipped, never allowed to break a real query."""
    config = config or {}
    kwargs: dict = {}
    top_k = config.get("top_k")
    if isinstance(top_k, int) and not isinstance(top_k, bool) and top_k >= 1:
        kwargs["top_k"] = top_k
    threshold = config.get("score_threshold")
    if isinstance(threshold, (int, float)) and not isinstance(threshold, bool) and 0.0 <= threshold <= 1.0:
        kwargs["score_threshold"] = float(threshold)
    strategy = RETRIEVAL_STRATEGY_ALIASES.get(config.get("strategy", config.get("retrieval_strategy")), config.get("strategy", config.get("retrieval_strategy")))
    if strategy in KNOWN_RETRIEVAL_STRATEGIES:
        kwargs["strategy"] = strategy
    reranker = config.get("reranker")
    if isinstance(reranker, str) and reranker.strip() and reranker != "none":
        kwargs["reranker"] = reranker
    overrides = {setting: config[flag] for flag, setting in _SETTINGS_FLAG_KEYS.items() if isinstance(config.get(flag), bool)}
    return kwargs, overrides
