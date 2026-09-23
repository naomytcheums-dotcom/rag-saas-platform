"""Phase 5, Étape 9 -- request/response bodies for
api/routers/mcp_servers.py."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class MCPServerCreateRequest(BaseModel):
    name: str
    description: str | None = None
    transport: str
    url: str | None = None
    command: str | None = None
    args: list[str] = []
    env: dict[str, str] = {}
    auth_type: str = "none"
    auth_credential: str | None = None


class MCPServerUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    auth_type: str | None = None
    auth_credential: str | None = None
    is_active: bool | None = None


class MCPServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    transport: str
    url: str | None
    command: str | None
    args: list
    auth_type: str
    is_active: bool
    last_sync_at: dt.datetime | None
    last_sync_error: str | None
    created_at: dt.datetime


class MCPToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    input_schema: dict
    discovered_at: dt.datetime


class MCPTestConnectionResponse(BaseModel):
    ok: bool
    tool_count: int
    checked_at: str


class MCPToolCallRequest(BaseModel):
    arguments: dict = {}


class MCPToolCallResponse(BaseModel):
    result: str
