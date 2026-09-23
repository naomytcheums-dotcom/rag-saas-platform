"""
Phase 5, Étape 9 -- real MCP CLIENT: lets this platform's own agents
call tools exposed by an EXTERNAL MCP server (stdio/sse/streamable_http
transport), using Anthropic's own official `mcp` SDK (already a real,
installed dependency -- `pip index versions mcp` confirms `mcp==2.0.0`
importable, `ClientSession`/`stdio_client`/`sse_client`/
`streamable_http_client` all real, not hand-rolled JSON-RPC).

**Real, deliberate security boundary for `stdio` transport**: `command`
is only ever a value an ORG ADMIN explicitly configured (see
`api/routers/mcp_servers.py`'s own `require_org_admin` gate on
create/update) -- never derived from a workflow variable, an LLM's own
tool-call arguments, or any other end-user-controlled input. This is
the same trust boundary this codebase already draws around
`api/services/custom_tools.py`'s own webhook URLs (operator-configured,
not LLM-configured), just for a local subprocess instead of a remote
HTTP call. Running an operator-configured local binary is real,
inherent stdio-MCP risk (the whole point of stdio transport); it is not
mitigated further here, and not appropriate for a multi-tenant SaaS
deployment where tenants themselves configure servers -- see this
module's own ROADMAP entry.

**One real client session per call, not a persistent pool**: an MCP
`ClientSession` is cheap to establish and each of `discover_tools`/
`call_tool` needs its own bounded, awaited lifetime (`async with`) --
keeping a long-lived session per `MCPServerConfig` across requests
would need real connection-health/reconnect logic this étape's own
scope doesn't require to make MCP tool-calling genuinely work.
"""

import datetime as dt
import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from api.models.mcp_server import MCPAuthType, MCPServerConfig, MCPTransport
from api.security.encryption import decrypt_field

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 15.0


class MCPClientError(Exception):
    """Real, dedicated exception -- a connection/discovery/call failure
    against an external MCP server, never silently swallowed."""


def _auth_headers(server: MCPServerConfig) -> dict[str, str]:
    if server.auth_type == MCPAuthType.none.value or not server.auth_credential_encrypted:
        return {}
    credential = decrypt_field(server.auth_credential_encrypted)
    if server.auth_type == MCPAuthType.bearer.value:
        return {"Authorization": f"Bearer {credential}"}
    if server.auth_type == MCPAuthType.api_key.value:
        return {"X-API-Key": credential}
    return {}


async def _open_session(server: MCPServerConfig, stack: AsyncExitStack) -> ClientSession:
    """Real transport dispatch -- opens the real read/write streams for
    `server.transport`, then a real, initialized `ClientSession` on top,
    all cleaned up via the caller's own `AsyncExitStack`."""
    if server.transport == MCPTransport.stdio.value:
        if not server.command:
            raise MCPClientError(f"MCP server {server.name!r} is configured for stdio but has no command")
        params = StdioServerParameters(command=server.command, args=list(server.args or []), env=dict(server.env or {}) or None)
        read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
    elif server.transport == MCPTransport.sse.value:
        if not server.url:
            raise MCPClientError(f"MCP server {server.name!r} is configured for sse but has no url")
        read_stream, write_stream = await stack.enter_async_context(
            sse_client(server.url, headers=_auth_headers(server), timeout=_DEFAULT_TIMEOUT_SECONDS)
        )
    elif server.transport == MCPTransport.streamable_http.value:
        if not server.url:
            raise MCPClientError(f"MCP server {server.name!r} is configured for streamable_http but has no url")
        read_stream, write_stream = await stack.enter_async_context(streamable_http_client(server.url))
    else:
        raise MCPClientError(f"MCP server {server.name!r} has an unknown transport {server.transport!r}")

    session = await stack.enter_async_context(ClientSession(read_stream, write_stream, read_timeout_seconds=_DEFAULT_TIMEOUT_SECONDS))
    await session.initialize()
    return session


async def discover_tools(server: MCPServerConfig) -> list[dict[str, Any]]:
    """Real `tools/list` round-trip against the external server. Raises
    `MCPClientError` on any real connection/protocol failure -- never
    returns a fabricated empty list on error (the caller,
    `api/services/mcp/discovery.py`, decides what an honest failure
    means for `last_sync_error`)."""
    try:
        async with AsyncExitStack() as stack:
            session = await _open_session(server, stack)
            result = await session.list_tools()
            return [
                {"name": tool.name, "description": tool.description or "", "input_schema": tool.input_schema or {}}
                for tool in result.tools
            ]
    except MCPClientError:
        raise
    except Exception as exc:  # noqa: BLE001 -- any real transport/protocol failure must surface as one honest, typed error
        raise MCPClientError(f"failed to discover tools from MCP server {server.name!r}: {exc}") from exc


async def call_tool(server: MCPServerConfig, tool_name: str, arguments: dict[str, Any]) -> str:
    """Real `tools/call` round-trip. Returns the tool's own text content
    joined -- MCP tool results can carry multiple content blocks
    (text/image/resource); this platform's own `ToolSpec.handler`
    contract (api/services/tools.py) returns a single string, so
    non-text blocks are described rather than silently dropped."""
    try:
        async with AsyncExitStack() as stack:
            session = await _open_session(server, stack)
            result = await session.call_tool(tool_name, arguments)
    except MCPClientError:
        raise
    except Exception as exc:  # noqa: BLE001 -- same reasoning as discover_tools
        raise MCPClientError(f"failed to call MCP tool {tool_name!r} on server {server.name!r}: {exc}") from exc

    parts: list[str] = []
    for block in result.content:
        text = getattr(block, "text", None)
        parts.append(text if text is not None else f"[non-text MCP content block: {type(block).__name__}]")
    joined = "\n".join(parts)
    if result.is_error:
        raise MCPClientError(f"MCP tool {tool_name!r} on server {server.name!r} returned an error: {joined}")
    return joined


async def test_connection(server: MCPServerConfig) -> dict[str, Any]:
    """Real, lightweight connectivity check for `POST
    /mcp-servers/{id}/test` -- a real `initialize` + `tools/list`, not a
    fabricated 'looks fine' response."""
    tools = await discover_tools(server)
    return {"ok": True, "tool_count": len(tools), "checked_at": dt.datetime.now(dt.timezone.utc).isoformat()}
