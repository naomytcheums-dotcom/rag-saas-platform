"""Request/response bodies for api/routers/tool_permissions.py (Partie 5.1.3)."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class ToolPermissionGrantRequest(BaseModel):
    user_id: uuid.UUID | None = None
    permission: str = Field(pattern="^(allow|deny)$")


class ToolPermissionResponse(BaseModel):
    id: uuid.UUID
    agent_id: str | None
    user_id: uuid.UUID | None
    tool_name: str
    permission: str
    created_by: uuid.UUID | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class AvailableToolResponse(BaseModel):
    name: str
    description: str
    parameters: dict[str, dict]
