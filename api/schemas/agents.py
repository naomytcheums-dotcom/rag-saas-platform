"""Request/response bodies for api/routers/agents.py (Partie 5.3.1).

`model_config_json`'s own JSON key stays `model_config` (item 1's own
literal field name) via a real Pydantic alias -- a plain FIELD cannot
be named `model_config` on a Pydantic model at all (Pydantic itself
reserves that exact name for the model's own class-level config)."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AgentCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str | None = None
    workspace_id: uuid.UUID | None = None
    system_prompt: str = "You are a helpful assistant."
    model_config_data: dict = Field(default_factory=dict, alias="model_config")
    tools: list[dict] = Field(default_factory=list)
    memory_enabled: bool = True
    memory_window_size: int = 10
    guardrails_enabled: bool = True
    human_approval_required: bool = False
    knowledge_base_id: uuid.UUID | None = None


class AgentUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    description: str | None = None
    workspace_id: uuid.UUID | None = None
    system_prompt: str | None = None
    model_config_data: dict | None = Field(default=None, alias="model_config")
    tools: list[dict] | None = None
    memory_enabled: bool | None = None
    memory_window_size: int | None = None
    guardrails_enabled: bool | None = None
    human_approval_required: bool | None = None
    knowledge_base_id: uuid.UUID | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    workspace_id: uuid.UUID | None
    name: str
    description: str | None
    system_prompt: str
    model_config_data: dict = Field(validation_alias="model_config_json", serialization_alias="model_config")
    tools: list
    memory_enabled: bool
    memory_window_size: int
    guardrails_enabled: bool
    human_approval_required: bool
    knowledge_base_id: uuid.UUID | None
    status: str
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


class SystemPromptUpdateRequest(BaseModel):
    system_prompt: str | None = None
    system_prompt_template: str | None = None


class SystemPromptPreviewResponse(BaseModel):
    rendered: str


class SystemPromptVariablesResponse(BaseModel):
    variables: list[str]


class AgentModelResponse(BaseModel):
    provider: str
    model: str
    temperature: float
    max_tokens: int
    top_p: float


class AgentModelUpdateRequest(BaseModel):
    provider: str
    model: str
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None


class AgentKnowledgeBaseResponse(BaseModel):
    knowledge_base_id: uuid.UUID | None
    config: dict


class AgentKnowledgeBaseUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    knowledge_base_id: uuid.UUID | None = None
    config: dict | None = None


class KnowledgeBaseOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
