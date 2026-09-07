"""
Partie 5.3.1 -- real agent CRUD + status transitions. Create/list are
org-scoped (`require_org_manager`/`require_org_member`, same tier
convention as `api/routers/workspaces.py`); get/update/delete/status
transitions resolve the agent AND the caller's real organization role
together (`require_agent_member`/`require_agent_manager`,
api/security/agents.py), since this étape's own literal paths for
those (`GET/PATCH/DELETE /agents/{agent_id}`) carry no `{org_id}`.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.agent import Agent
from api.models.organization import OrganizationMember
from api.schemas.agents import AgentCreateRequest, AgentResponse, AgentUpdateRequest
from api.security.agents import (
    activate_agent, archive_agent, create_agent, delete_agent, list_agents, pause_agent, require_agent_manager,
    require_agent_member, update_agent,
)
from api.security.organizations import require_org_manager, require_org_member
from api.security.quotas import require_quota_available

router = APIRouter(tags=["agents"])


@router.post("/organizations/{org_id}/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_endpoint(
    org_id: uuid.UUID, payload: AgentCreateRequest,
    caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    await require_quota_available(db, org_id, "agents")  # Partie 1.3.6, real live count since Partie 5.3.1
    agent = await create_agent(db, org_id, payload.model_dump(by_alias=True), caller.user_id)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/organizations/{org_id}/agents", response_model=list[AgentResponse])
async def list_agents_endpoint(
    org_id: uuid.UUID, status_filter: str | None = Query(default=None, alias="status"), workspace_id: uuid.UUID | None = None,
    limit: int = Query(default=50, le=200), offset: int = Query(default=0, ge=0),
    _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db),
):
    filters = {}
    if status_filter is not None:
        filters["status"] = status_filter
    if workspace_id is not None:
        filters["workspace_id"] = workspace_id
    return await list_agents(db, org_id, filters=filters, limit=limit, offset=offset)


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent_endpoint(agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_member)):
    agent, _caller = agent_ctx
    return agent


@router.patch("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent_endpoint(
    payload: AgentUpdateRequest,
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    updated = await update_agent(db, agent.id, payload.model_dump(by_alias=True, exclude_unset=True))
    await db.commit()
    await db.refresh(updated)
    return updated


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    await delete_agent(db, agent.id)
    await db.commit()


@router.post("/agents/{agent_id}/activate", response_model=AgentResponse)
async def activate_agent_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    updated = await activate_agent(db, agent.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/agents/{agent_id}/pause", response_model=AgentResponse)
async def pause_agent_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    updated = await pause_agent(db, agent.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/agents/{agent_id}/archive", response_model=AgentResponse)
async def archive_agent_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    updated = await archive_agent(db, agent.id)
    await db.commit()
    await db.refresh(updated)
    return updated
