"""Request/response bodies for api/routers/workflows.py (Partie 5.4.1)."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class WorkflowCreateRequest(BaseModel):
    name: str
    description: str | None = None
    workspace_id: uuid.UUID | None = None
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)


class WorkflowUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    workspace_id: uuid.UUID | None = None
    nodes: list[dict] | None = None
    edges: list[dict] | None = None
    status: str | None = None


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    workspace_id: uuid.UUID | None
    name: str
    description: str | None
    nodes: list
    edges: list
    status: str
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


class WorkflowValidateResponse(BaseModel):
    valid: bool
    errors: list[str]
