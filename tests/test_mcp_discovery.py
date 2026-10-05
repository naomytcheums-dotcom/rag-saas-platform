"""api/services/mcp/discovery.py's `call_cached_tool` -- Systèmes
internes, item 23 (MCP Firewall) wiring. Mocked at the real, already-
tested `call_tool_with_firewall` boundary (tests/test_mcp_firewall.py
covers ITS OWN real policy+audit logic) -- this test only verifies
`call_cached_tool` actually routes through it with the right real
arguments, never re-tests the firewall itself."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from api.services.mcp.discovery import call_cached_tool


async def test_call_cached_tool_routes_through_the_real_firewall():
    server = MagicMock()
    server.organization_id = uuid.uuid4()
    server.name = "test-server"
    user_id = uuid.uuid4()

    mock_firewall = AsyncMock(return_value="real tool output")
    with patch("api.services.mcp.firewall.call_tool_with_firewall", mock_firewall):
        result = await call_cached_tool(
            MagicMock(), server, "search", {"q": "hello"}, user_id=user_id, ip="1.2.3.4", user_agent="pytest",
        )

    assert result == "real tool output"
    mock_firewall.assert_awaited_once()
    call_args = mock_firewall.call_args
    assert call_args.args[1] == server.organization_id
    assert call_args.args[2] == user_id
    assert call_args.args[3] is server
    assert call_args.args[4] == "search"
    assert call_args.args[5] == {"q": "hello"}
    assert call_args.kwargs == {"ip": "1.2.3.4", "user_agent": "pytest"}


async def test_call_cached_tool_defaults_user_id_to_none_for_a_system_initiated_call():
    """Validation criterion: the real agent-tools call site
    (api/services/agent_tools.py) has no synchronous real end-user to
    attribute the call to -- `user_id=None` must flow through honestly,
    not be rejected or fabricated."""
    server = MagicMock()
    server.organization_id = uuid.uuid4()

    mock_firewall = AsyncMock(return_value="ok")
    with patch("api.services.mcp.firewall.call_tool_with_firewall", mock_firewall):
        await call_cached_tool(MagicMock(), server, "search", {})

    assert mock_firewall.call_args.args[2] is None
