"""
Phase 5, Étape 9 -- real CRUD + discovery/call for this org's own
registered EXTERNAL MCP servers (the MCP CLIENT role -- see
api/models/mcp_server.py's own docstring for the split from this
platform's own MCP SERVER role, api/routers/mcp_server.py).

Create/update/delete/test-connection/sync are Admin+-gated (same tier
as `custom_domains.py`'s own POST/DELETE -- registering a subprocess
command or an external URL an agent will call tools from is an
organization-level trust decision, not a per-member one). Listing
servers/tools is Member+-readable, same reasoning as most other
org-scoped config surfaces (a member composing an agent needs to see
what's available without needing Admin).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.mcp_server import MCPServerConfig
from api.models.organization import OrganizationMember
from api.schemas.mcp_servers import (
    MCPServerCreateRequest, MCPServerResponse, MCPServerUpdateRequest, MCPTestConnectionResponse, MCPToolCallRequest,
    MCPToolCallResponse, MCPToolResponse,
)
from api.security.permissions import require_permission
from api.security.encryption import encrypt_field
from api.security.organizations import require_org_admin, require_org_member
from api.services.mcp.client import MCPClientError, test_connection
from api.services.mcp.discovery import (
    call_cached_tool, create_mcp_server, delete_mcp_server, list_cached_tools, list_mcp_servers, sync_tools,
)

router = APIRouter(tags=["mcp-servers"])

_VALID_TRANSPORTS = ("stdio", "sse", "streamable_http")
_VALID_AUTH_TYPES = ("none", "bearer", "api_key")


async def _get_owned_server(db: AsyncSession, org_id: uuid.UUID, server_id: uuid.UUID) -> MCPServerConfig:
    server = await db.get(MCPServerConfig, server_id)
    if server is None or server.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return server


@router.post("/organizations/{org_id}/mcp-servers", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_server_endpoint(
    org_id: uuid.UUID, payload: MCPServerCreateRequest,
    caller: OrganizationMember = Depends(require_permission("integrations:manage")), db: AsyncSession = Depends(get_db),
):
    if payload.transport not in _VALID_TRANSPORTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"transport must be one of {_VALID_TRANSPORTS}")
    if payload.auth_type not in _VALID_AUTH_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"auth_type must be one of {_VALID_AUTH_TYPES}")
    if payload.transport == "stdio" and not payload.command:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="command is required for the stdio transport")
    if payload.transport in ("sse", "streamable_http") and not payload.url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"url is required for the {payload.transport} transport")

    server = await create_mcp_server(
        db, org_id, name=payload.name, description=payload.description, transport=payload.transport, url=payload.url,
        command=payload.command, args=payload.args, env=payload.env, auth_type=payload.auth_type,
        auth_credential=payload.auth_credential, created_by=caller.user_id,
    )
    await db.commit()
    return server


@router.get("/organizations/{org_id}/mcp-servers", response_model=list[MCPServerResponse])
async def list_mcp_servers_endpoint(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("integrations:read")), db: AsyncSession = Depends(get_db),
):
    return await list_mcp_servers(db, org_id)


@router.patch("/organizations/{org_id}/mcp-servers/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server_endpoint(
    org_id: uuid.UUID, server_id: uuid.UUID, payload: MCPServerUpdateRequest,
    _caller: OrganizationMember = Depends(require_permission("integrations:manage")), db: AsyncSession = Depends(get_db),
):
    server = await _get_owned_server(db, org_id, server_id)
    for field in ("name", "description", "url", "command", "args", "env", "auth_type", "is_active"):
        value = getattr(payload, field)
        if value is not None:
            setattr(server, field, value)
    if payload.auth_credential is not None:
        server.auth_credential_encrypted = encrypt_field(payload.auth_credential) if payload.auth_credential else None
    await db.commit()
    return server


@router.delete("/organizations/{org_id}/mcp-servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server_endpoint(
    org_id: uuid.UUID, server_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("integrations:manage")), db: AsyncSession = Depends(get_db),
):
    server = await _get_owned_server(db, org_id, server_id)
    await delete_mcp_server(db, server)
    await db.commit()


@router.post("/organizations/{org_id}/mcp-servers/{server_id}/test", response_model=MCPTestConnectionResponse)
async def test_mcp_server_endpoint(
    org_id: uuid.UUID, server_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("integrations:manage")), db: AsyncSession = Depends(get_db),
):
    server = await _get_owned_server(db, org_id, server_id)
    try:
        return await test_connection(server)
    except MCPClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.get("/organizations/{org_id}/mcp-servers/{server_id}/tools", response_model=list[MCPToolResponse])
async def list_mcp_tools_endpoint(
    org_id: uuid.UUID, server_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("integrations:read")), db: AsyncSession = Depends(get_db),
):
    server = await _get_owned_server(db, org_id, server_id)
    return await list_cached_tools(db, server.id)


@router.post("/organizations/{org_id}/mcp-servers/{server_id}/sync", response_model=list[MCPToolResponse])
async def sync_mcp_tools_endpoint(
    org_id: uuid.UUID, server_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("integrations:manage")), db: AsyncSession = Depends(get_db),
):
    server = await _get_owned_server(db, org_id, server_id)
    try:
        rows = await sync_tools(db, server)
    except MCPClientError as exc:
        await db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    await db.commit()
    return rows


@router.post("/organizations/{org_id}/mcp-servers/{server_id}/tools/{tool_name}/call", response_model=MCPToolCallResponse)
async def call_mcp_tool_endpoint(
    org_id: uuid.UUID, server_id: uuid.UUID, tool_name: str, payload: MCPToolCallRequest,
    _caller: OrganizationMember = Depends(require_permission("integrations:write")), db: AsyncSession = Depends(get_db),
):
    server = await _get_owned_server(db, org_id, server_id)
    try:
        result = await call_cached_tool(db, server, tool_name, payload.arguments)
    except MCPClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return MCPToolCallResponse(result=result)
