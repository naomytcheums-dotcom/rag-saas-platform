"""Phase 5, Étape 9 -- real CRUD + tool-discovery sync for
`MCPServerConfig`/`MCPToolCache` (api/models/mcp_server.py). Separate
from api/services/mcp/client.py's own low-level protocol calls -- this
module owns the real DB bookkeeping (create/list/sync/delete),
`client.py` owns talking to the actual external server."""

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.mcp_server import MCPServerConfig, MCPToolCache
from api.security.encryption import encrypt_field
from api.services.mcp.client import MCPClientError, call_tool, discover_tools


async def create_mcp_server(
    db: AsyncSession, organization_id: uuid.UUID, *, name: str, transport: str, description: str | None = None,
    url: str | None = None, command: str | None = None, args: list | None = None, env: dict | None = None,
    auth_type: str = "none", auth_credential: str | None = None, created_by: uuid.UUID | None = None,
) -> MCPServerConfig:
    server = MCPServerConfig(
        organization_id=organization_id, name=name, description=description, transport=transport, url=url,
        command=command, args=args or [], env=env or {}, auth_type=auth_type,
        auth_credential_encrypted=encrypt_field(auth_credential) if auth_credential else None, created_by=created_by,
    )
    db.add(server)
    await db.flush()
    return server


async def list_mcp_servers(db: AsyncSession, organization_id: uuid.UUID) -> list[MCPServerConfig]:
    result = await db.scalars(select(MCPServerConfig).where(MCPServerConfig.organization_id == organization_id).order_by(MCPServerConfig.created_at))
    return list(result.all())


async def delete_mcp_server(db: AsyncSession, server: MCPServerConfig) -> None:
    await db.delete(server)
    await db.flush()


async def sync_tools(db: AsyncSession, server: MCPServerConfig) -> list[MCPToolCache]:
    """Real `tools/list` against the live server, replacing the cached
    snapshot atomically. On a real failure, records `last_sync_error`
    (honest, visible to the org admin) and re-raises -- never silently
    leaves a stale cache looking current."""
    try:
        discovered = await discover_tools(server)
    except MCPClientError as exc:
        server.last_sync_error = str(exc)
        server.last_sync_at = dt.datetime.now(dt.timezone.utc)
        await db.flush()
        raise

    await db.execute(delete(MCPToolCache).where(MCPToolCache.server_id == server.id))
    rows = [
        MCPToolCache(server_id=server.id, name=tool["name"], description=tool["description"], input_schema=tool["input_schema"])
        for tool in discovered
    ]
    db.add_all(rows)
    server.last_sync_error = None
    server.last_sync_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return rows


async def list_cached_tools(db: AsyncSession, server_id: uuid.UUID) -> list[MCPToolCache]:
    result = await db.scalars(select(MCPToolCache).where(MCPToolCache.server_id == server_id).order_by(MCPToolCache.name))
    return list(result.all())


async def call_cached_tool(db: AsyncSession, server: MCPServerConfig, tool_name: str, arguments: dict[str, Any]) -> str:
    """Real `tools/call` -- `server` must belong to the caller's own
    organization (enforced by the router dependency, not here)."""
    return await call_tool(server, tool_name, arguments)
