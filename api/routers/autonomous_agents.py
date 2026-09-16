"""Partie 23 -- autonomous agent endpoints. Org-scoped list/create
routes reuse `require_org_member`/`require_org_admin` directly;
single-resource routes use `require_autonomous_agent_member`/
`require_autonomous_agent_admin` (api/security/autonomous_agents.py),
a flat `/autonomous-agents/{id}` path -- same access-level adaptation
already applied for Parties 19-22."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.autonomous_agent import AutonomousAgent
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.autonomous_agent import (
    AgentCollaborationRequest, AgentCollaborationResponse, AgentCostResponse, AgentMemoryCreateRequest, AgentMemoryResponse,
    AgentPlanResponse, AgentStatusResponse, AgentStepResponse, AutonomousAgentCreateRequest, AutonomousAgentListResponse,
    AutonomousAgentResponse, AutonomousAgentUpdateRequest,
)
from api.security.autonomous_agents import require_autonomous_agent_admin, require_autonomous_agent_member
from api.security.organizations import require_org_admin, require_org_member
from api.services import autonomous_agents as autonomous_agents_service
from api.tasks.autonomous_agents import schedule_autonomous_agent_run

router = APIRouter(tags=["autonomous-agents"])


@router.get("/organizations/{org_id}/autonomous-agents", response_model=AutonomousAgentListResponse)
async def list_autonomous_agents_endpoint(
    org_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db),
):
    return await autonomous_agents_service.list_autonomous_agents(db, org_id, limit, offset)


@router.post("/organizations/{org_id}/autonomous-agents", response_model=AutonomousAgentResponse, status_code=status.HTTP_201_CREATED)
async def create_autonomous_agent_endpoint(
    org_id: uuid.UUID, payload: AutonomousAgentCreateRequest, _caller: OrganizationMember = Depends(require_org_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    agent = await autonomous_agents_service.create_autonomous_agent(db, org_id, payload.model_dump(), current_user.id)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/autonomous-agents/{agent_id}", response_model=AutonomousAgentResponse)
async def get_autonomous_agent_endpoint(agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member)):
    agent, _caller = agent_ctx
    return agent


@router.patch("/autonomous-agents/{agent_id}", response_model=AutonomousAgentResponse)
async def update_autonomous_agent_endpoint(
    payload: AutonomousAgentUpdateRequest, agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_admin),
    db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    updated = await autonomous_agents_service.update_autonomous_agent(db, agent.id, payload.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(updated)
    return updated


@router.delete("/autonomous-agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_autonomous_agent_endpoint(agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_admin), db: AsyncSession = Depends(get_db)):
    agent, _caller = agent_ctx
    await autonomous_agents_service.delete_autonomous_agent(db, agent.id)
    await db.commit()


# --------------------------------------------------------------- execution

@router.post("/autonomous-agents/{agent_id}/run", response_model=AutonomousAgentResponse)
async def run_autonomous_agent_endpoint(agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db)):
    agent, _caller = agent_ctx
    schedule_autonomous_agent_run(agent.id)
    await db.refresh(agent)
    return agent


@router.post("/autonomous-agents/{agent_id}/pause", response_model=AutonomousAgentResponse)
async def pause_autonomous_agent_endpoint(agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db)):
    agent, _caller = agent_ctx
    updated = await autonomous_agents_service.pause_autonomous_agent(db, agent.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/autonomous-agents/{agent_id}/resume", response_model=AutonomousAgentResponse)
async def resume_autonomous_agent_endpoint(agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db)):
    agent, _caller = agent_ctx
    schedule_autonomous_agent_run(agent.id)
    await db.refresh(agent)
    return agent


@router.post("/autonomous-agents/{agent_id}/stop", response_model=AutonomousAgentResponse)
async def stop_autonomous_agent_endpoint(agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db)):
    agent, _caller = agent_ctx
    updated = await autonomous_agents_service.stop_autonomous_agent(db, agent.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.get("/autonomous-agents/{agent_id}/status", response_model=AgentStatusResponse)
async def get_autonomous_agent_status_endpoint(agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db)):
    agent, _caller = agent_ctx
    return await autonomous_agents_service.get_agent_status(db, agent.id)


@router.get("/autonomous-agents/{agent_id}/cost", response_model=AgentCostResponse)
async def get_autonomous_agent_cost_endpoint(agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db)):
    agent, _caller = agent_ctx
    return await autonomous_agents_service.get_agent_cost(db, agent.id)


# --------------------------------------------------------------- planning

@router.get("/autonomous-agents/{agent_id}/plans", response_model=list[AgentPlanResponse])
async def list_agent_plans_endpoint(agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db)):
    agent, _caller = agent_ctx
    return await autonomous_agents_service.list_agent_plans(db, agent.id)


@router.get("/autonomous-agents/{agent_id}/plans/{plan_id}", response_model=AgentPlanResponse)
async def get_agent_plan_endpoint(
    plan_id: uuid.UUID, agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    plan = await autonomous_agents_service.get_agent_plan(db, plan_id)
    if plan is None or plan.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return plan


@router.get("/autonomous-agents/{agent_id}/plans/{plan_id}/steps", response_model=list[AgentStepResponse])
async def list_agent_steps_endpoint(
    plan_id: uuid.UUID, agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    plan = await autonomous_agents_service.get_agent_plan(db, plan_id)
    if plan is None or plan.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return await autonomous_agents_service.list_agent_steps(db, plan_id)


# --------------------------------------------------------------- memory

@router.get("/autonomous-agents/{agent_id}/memory", response_model=list[AgentMemoryResponse])
async def get_agent_memory_endpoint(
    memory_type: str | None = None, agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    return await autonomous_agents_service.get_agent_memory(db, agent.id, memory_type)


@router.post("/autonomous-agents/{agent_id}/memory", response_model=AgentMemoryResponse, status_code=status.HTTP_201_CREATED)
async def add_agent_memory_endpoint(
    payload: AgentMemoryCreateRequest, agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    memory = await autonomous_agents_service.add_agent_memory(db, agent.id, payload.content, payload.memory_type, payload.importance)
    await db.commit()
    await db.refresh(memory)
    return memory


@router.delete("/autonomous-agents/{agent_id}/memory/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_memory_endpoint(
    memory_id: uuid.UUID, agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db),
):
    _agent, _caller = agent_ctx
    await autonomous_agents_service.delete_agent_memory(db, memory_id)
    await db.commit()


# --------------------------------------------------------------- collaboration

@router.post("/autonomous-agents/{agent_id}/collaborate", response_model=AgentCollaborationResponse, status_code=status.HTTP_201_CREATED)
async def collaborate_endpoint(
    payload: AgentCollaborationRequest, agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    collaboration = await autonomous_agents_service.collaborate_agents(db, agent.id, payload.collaborator_agent_id, payload.task)
    await autonomous_agents_service.accept_collaboration(db, collaboration.id)
    await autonomous_agents_service.execute_collaboration(db, collaboration.id)
    await db.commit()
    await db.refresh(collaboration)
    return collaboration


@router.get("/autonomous-agents/{agent_id}/collaborations", response_model=list[AgentCollaborationResponse])
async def list_collaborations_endpoint(agent_ctx: tuple[AutonomousAgent, OrganizationMember] = Depends(require_autonomous_agent_member), db: AsyncSession = Depends(get_db)):
    agent, _caller = agent_ctx
    return await autonomous_agents_service.list_collaborations(db, agent.id)
