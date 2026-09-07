"""Request/response bodies for the Partie 5.4.2 trigger/run endpoints."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class WorkflowTriggerCreateRequest(BaseModel):
    type: str
    config: dict = Field(default_factory=dict)


class WorkflowTriggerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    type: str
    config: dict
    webhook_token: str | None
    created_at: dt.datetime


class WorkflowRunRequest(BaseModel):
    input: dict = Field(default_factory=dict)


class WorkflowRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    trigger_id: uuid.UUID | None
    status: str
    input: dict | None
    output: dict | None
    error: str | None
    started_at: dt.datetime
    completed_at: dt.datetime | None
