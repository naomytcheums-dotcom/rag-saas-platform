"""Request/response bodies for api/routers/workspaces.py (Etape 1.2.4)."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class WorkspaceCreateRequest(BaseModel):
    """Body of POST /organizations/{org_id}/workspaces."""

    name: str = Field(min_length=1, max_length=200)


class WorkspaceUpdateRequest(BaseModel):
    """Body of PATCH /workspaces/{workspace_id}."""

    name: str = Field(min_length=1, max_length=200)


class WorkspaceEntry(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceEntry]
