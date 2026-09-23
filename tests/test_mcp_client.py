"""Phase 5, Étape 9 -- real MCP client tests, run against a real,
minimal MCP server subprocess (tests/mcp_test_server.py), not fixtures
shaped to match the client's own assumptions. Per the token-management
rule, this real subprocess round-trip runs once per test, not per
assertion -- no full external infra, just a tiny real stdio server."""

import sys
from pathlib import Path

import pytest

from api.models.mcp_server import MCPServerConfig
from api.services.mcp.client import MCPClientError, call_tool, discover_tools
from api.services.mcp.client import test_connection as mcp_test_connection

_SERVER_SCRIPT = str(Path(__file__).resolve().parent / "mcp_test_server.py")


def _stdio_server() -> MCPServerConfig:
    return MCPServerConfig(
        organization_id=None, name="test-stdio-server", transport="stdio",
        command=sys.executable, args=[_SERVER_SCRIPT], env={},
    )


async def test_discover_tools_against_a_real_stdio_mcp_server():
    """Validation criterion: un vrai tools/list contre un vrai serveur."""
    tools = await discover_tools(_stdio_server())

    names = {tool["name"] for tool in tools}
    assert names == {"add", "fail"}
    add_tool = next(t for t in tools if t["name"] == "add")
    assert add_tool["input_schema"]["properties"].keys() == {"a", "b"}


async def test_call_tool_against_a_real_stdio_mcp_server():
    """Validation criterion: un vrai tools/call contre un vrai serveur."""
    result = await call_tool(_stdio_server(), "add", {"a": 2, "b": 3})

    assert result == "5"


async def test_call_tool_surfaces_a_real_tool_error():
    with pytest.raises(MCPClientError):
        await call_tool(_stdio_server(), "fail", {})


async def test_call_tool_raises_for_an_unknown_tool_name():
    with pytest.raises(MCPClientError):
        await call_tool(_stdio_server(), "does_not_exist", {})


async def test_test_connection_reports_the_real_tool_count():
    result = await mcp_test_connection(_stdio_server())

    assert result == {"ok": True, "tool_count": 2, "checked_at": result["checked_at"]}


async def test_discover_tools_raises_for_a_missing_command():
    server = MCPServerConfig(organization_id=None, name="broken", transport="stdio", command=None, args=[], env={})

    with pytest.raises(MCPClientError):
        await discover_tools(server)


async def test_discover_tools_raises_for_an_unreachable_url_transport():
    server = MCPServerConfig(
        organization_id=None, name="unreachable", transport="streamable_http", url="http://127.0.0.1:1/mcp", args=[], env={},
    )

    with pytest.raises(MCPClientError):
        await discover_tools(server)
