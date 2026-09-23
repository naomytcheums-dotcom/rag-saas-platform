"""Phase 5, Étape 9 -- a real, minimal MCP server run as a stdio
subprocess by tests/test_mcp_client.py, using the exact same `mcp` SDK
this platform's own client (api/services/mcp/client.py) talks to. Not a
mock of the protocol -- a real server, so the client is proven against
a real `initialize`/`tools/list`/`tools/call` round-trip, not fixtures
shaped to match the client's own assumptions."""

from mcp.server.mcpserver import MCPServer

server = MCPServer("test-server")


@server.tool()
def add(a: int, b: int) -> str:
    """Add two real numbers."""
    return str(a + b)


@server.tool()
def fail() -> str:
    """Always real-fails, to prove error propagation."""
    raise RuntimeError("deliberate real test failure")


if __name__ == "__main__":
    server.run()
