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
