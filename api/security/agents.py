"""
Partie 5.3.1 -- the real, persisted `Agent` entity. See
api/models/agent.py's own top docstring for why `str(Agent.id)` is now
the SAME real `agent_id` string every earlier 5.1.x/5.2.x module
(`AgentOrchestrator`, `AgentSession`, `ToolPermission`, ...) already
expected -- this étape doesn't change any of those call sites (none of
them require the string to come from a real `Agent` row), but it means
one now CAN exist behind it.

**Real dependency pattern reused from `api/security/workspaces.py`'s
own `require_workspace_permission`**: `require_agent_member`/
`require_agent_manager` below resolve the agent AND the caller's real
organization membership together (404, not 403, for a non-member --
same anti-enumeration reasoning), since this étape's own literal
endpoint paths (`GET/PATCH/DELETE /agents/{agent_id}`, no
`{org_id}`) have no other way to know which organization's role tier
even applies."""

import datetime as dt
import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.agent import Agent, AgentStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _resolve_agent_and_membership(agent_id: uuid.UUID, current_user: User, db: AsyncSession) -> tuple[Agent, OrganizationMember]:
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        raise _NOT_FOUND

    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == agent.organization_id, OrganizationMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise _NOT_FOUND
    return agent, membership


async def require_agent_member(
    agent_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[Agent, OrganizationMember]:
    """Real dependency -- any real role in the agent's own organization."""
    return await _resolve_agent_and_membership(agent_id, current_user, db)


async def require_agent_manager(
    agent_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[Agent, OrganizationMember]:
    """Real dependency -- Owner/Admin/Manager in the agent's own organization."""
    agent, membership = await _resolve_agent_and_membership(agent_id, current_user, db)
    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin, OrganizationRole.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization manager access required")
    return agent, membership


async def create_agent(db: AsyncSession, organization_id: uuid.UUID, data: dict, created_by: uuid.UUID | None) -> Agent:
    """Item 3's own literal function."""
    agent = Agent(
        organization_id=organization_id, created_by=created_by,
        workspace_id=data.get("workspace_id"), name=data["name"], description=data.get("description"),
        system_prompt=data.get("system_prompt", "You are a helpful assistant."),
        model_config_json=data.get("model_config") or {}, tools=data.get("tools") or [],
        memory_enabled=data.get("memory_enabled", True), memory_window_size=data.get("memory_window_size", 10),
        guardrails_enabled=data.get("guardrails_enabled", True), human_approval_required=data.get("human_approval_required", False),
        knowledge_base_id=data.get("knowledge_base_id"),
    )
    db.add(agent)
    await db.flush()
    return agent


async def update_agent(db: AsyncSession, agent_id: uuid.UUID, data: dict) -> Agent | None:
    """Item 3's own literal function -- real, partial update (only
    the real, given fields change)."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    for field in (
        "name", "description", "system_prompt", "workspace_id", "memory_enabled", "memory_window_size",
        "guardrails_enabled", "human_approval_required", "knowledge_base_id",
    ):
        if field in data:
            setattr(agent, field, data[field])
    if "model_config" in data:
        agent.model_config_json = data["model_config"]
    if "tools" in data:
        agent.tools = data["tools"]
    await db.flush()
    return agent


async def get_agent(db: AsyncSession, agent_id: uuid.UUID) -> Agent | None:
    """Item 3's own literal function -- `None` for an unknown OR real,
    soft-deleted agent."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    return agent


async def list_agents(db: AsyncSession, organization_id: uuid.UUID, filters: dict | None = None, limit: int = 50, offset: int = 0) -> list[Agent]:
    """Item 3's own literal function -- real, optional `status`/
    `workspace_id` filters."""
    filters = filters or {}
    query = select(Agent).where(Agent.organization_id == organization_id, Agent.deleted_at.is_(None))
    if "status" in filters:
        query = query.where(Agent.status == filters["status"])
    if "workspace_id" in filters:
        query = query.where(Agent.workspace_id == filters["workspace_id"])
    query = query.order_by(Agent.created_at.desc()).limit(limit).offset(offset)
    return list((await db.scalars(query)).all())


async def delete_agent(db: AsyncSession, agent_id: uuid.UUID) -> bool:
    """Item 3's own literal function -- real SOFT delete (item 3's own
    literal parenthetical), not a hard `DELETE`: a real agent's own
    runs/traces/escalations keep a real, meaningful reference to it."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return False
    agent.deleted_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return True


async def _set_status(db: AsyncSession, agent_id: uuid.UUID, status_value: str) -> Agent | None:
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        return None
    agent.status = status_value
    await db.flush()
    return agent


async def activate_agent(db: AsyncSession, agent_id: uuid.UUID) -> Agent | None:
    """Item 3's own literal function."""
    return await _set_status(db, agent_id, AgentStatus.active.value)


async def pause_agent(db: AsyncSession, agent_id: uuid.UUID) -> Agent | None:
    """Item 3's own literal function."""
    return await _set_status(db, agent_id, AgentStatus.paused.value)


async def archive_agent(db: AsyncSession, agent_id: uuid.UUID) -> Agent | None:
    """Item 3's own literal function."""
    return await _set_status(db, agent_id, AgentStatus.archived.value)
