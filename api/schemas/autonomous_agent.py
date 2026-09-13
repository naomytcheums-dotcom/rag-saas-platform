"""Partie 23 -- request/response bodies for api/routers/autonomous_agents.py."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class AutonomousAgentCreateRequest(BaseModel):
    name: str
    description: str | None = None
    goal: str
    max_steps: int | None = None
    tools_enabled: list[dict] | None = None
    guardrails: dict | None = None
    memory_config: dict | None = None


class AutonomousAgentUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    goal: str | None = None
    max_steps: int | None = None
    tools_enabled: list[dict] | None = None
    guardrails: dict | None = None
    memory_config: dict | None = None


class AutonomousAgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: uuid.UUID | None
    name: str
    description: str | None
    goal: str
    status: str
    max_steps: int
    current_step: int
    tools_enabled: list
    guardrails: dict
    memory_config: dict
    error: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class AutonomousAgentListResponse(BaseModel):
    items: list[AutonomousAgentResponse]
    total: int
    limit: int
    offset: int


class AgentStatusResponse(BaseModel):
    status: str
    current_step: int
    max_steps: int
    error: str | None


class AgentPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    goal: str
    steps: list
    status: str
    created_at: dt.datetime


class AgentStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    step_number: int
    action: str
    parameters: dict | None
    result: dict | None
    status: str
    error: str | None
    started_at: dt.datetime | None
    completed_at: dt.datetime | None


class AgentMemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    memory_type: str
    content: str
    importance: float
    created_at: dt.datetime


class AgentMemoryCreateRequest(BaseModel):
    content: str
    memory_type: str = "short_term"
    importance: float = 0.5


class AgentCollaborationRequest(BaseModel):
    collaborator_agent_id: uuid.UUID
    task: str


class AgentCollaborationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    initiator_agent_id: uuid.UUID
    collaborator_agent_id: uuid.UUID
    task: str
    status: str
    result: dict | None
    created_at: dt.datetime
