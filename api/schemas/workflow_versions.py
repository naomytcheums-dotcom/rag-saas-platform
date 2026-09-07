"""Request/response bodies for the Partie 5.4.13 workflow-versioning endpoints."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class WorkflowVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    version_number: int
    nodes: list
    edges: list
    created_by: uuid.UUID | None
    created_at: dt.datetime
    comment: str | None


class WorkflowVersionCreateRequest(BaseModel):
    comment: str | None = None


class WorkflowVersionRestoreRequest(BaseModel):
    version_number: int


class WorkflowVersionDiffRequest(BaseModel):
    version_a: int
    version_b: int


class WorkflowVersionDiffItem(BaseModel):
    added: list[str]
    removed: list[str]
    changed: list[str]


class WorkflowVersionDiffResponse(BaseModel):
    nodes: WorkflowVersionDiffItem
    edges: WorkflowVersionDiffItem
