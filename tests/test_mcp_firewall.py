"""api/services/mcp/firewall.py -- real orchestration over 3 already-
tested boundaries: `check_policy` (item 13), `call_tool` (real MCP
transport, already covered by tests/test_mcp_client.py), and
`log_audit_action` (real, tamper-evident audit log, already covered by
its own dedicated test module). Mocked at all 3 -- this test module
verifies the real firewall ORDER and DECISION logic (policy check ->
execute -> audit), never re-tests any of the 3 underlying systems."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.mcp.firewall import call_tool_with_firewall


def _fake_server():
    server = MagicMock()
    server.name = "test-server"
    return server


async def test_call_tool_with_firewall_executes_and_audits_a_real_allowed_call(db_session):
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    server = _fake_server()

    mock_check_policy = AsyncMock(return_value=True)
    mock_call_tool = AsyncMock(return_value="real tool output")
    mock_log_audit = AsyncMock()

    with patch("api.services.opa_policy.check_policy", mock_check_policy), \
         patch("api.services.mcp.client.call_tool", mock_call_tool), \
         patch("api.security.audit_log.log_audit_action", mock_log_audit):
        result = await call_tool_with_firewall(db_session, org_id, user_id, server, "search", {"q": "hello"})

    assert result == "real tool output"
    mock_call_tool.assert_awaited_once_with(server, "search", {"q": "hello"})
    mock_log_audit.assert_awaited_once()
    assert mock_log_audit.call_args.kwargs["success"] is True


async def test_call_tool_with_firewall_blocks_and_audits_a_real_policy_denial(db_session):
    from api.services.mcp.client import MCPClientError

    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    server = _fake_server()

    mock_check_policy = AsyncMock(return_value=False)
    mock_call_tool = AsyncMock()
    mock_log_audit = AsyncMock()

    with patch("api.services.opa_policy.check_policy", mock_check_policy), \
         patch("api.services.mcp.client.call_tool", mock_call_tool), \
         patch("api.security.audit_log.log_audit_action", mock_log_audit):
        with pytest.raises(MCPClientError):
            await call_tool_with_firewall(db_session, org_id, user_id, server, "dangerous_tool", {})

    mock_call_tool.assert_not_awaited()
    mock_log_audit.assert_awaited_once()
    assert mock_log_audit.call_args.kwargs["success"] is False
    assert "blocked by OPA policy" in mock_log_audit.call_args.kwargs["failure_reason"]


async def test_call_tool_with_firewall_executes_when_policy_is_disabled_fail_open(db_session):
    """Validation criterion: OPA disabled/unreachable (real `None` from
    check_policy) must never block a real tool call -- same fail-open
    discipline as item 13's own check_policy contract."""
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    server = _fake_server()

    with patch("api.services.opa_policy.check_policy", AsyncMock(return_value=None)), \
         patch("api.services.mcp.client.call_tool", AsyncMock(return_value="ok")), \
         patch("api.security.audit_log.log_audit_action", AsyncMock()):
        result = await call_tool_with_firewall(db_session, org_id, user_id, server, "search", {})

    assert result == "ok"


async def test_call_tool_with_firewall_audits_a_real_execution_failure_and_reraises(db_session):
    from api.services.mcp.client import MCPClientError

    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    server = _fake_server()
    mock_log_audit = AsyncMock()

    with patch("api.services.opa_policy.check_policy", AsyncMock(return_value=True)), \
         patch("api.services.mcp.client.call_tool", AsyncMock(side_effect=MCPClientError("real transport failure"))), \
         patch("api.security.audit_log.log_audit_action", mock_log_audit):
        with pytest.raises(MCPClientError, match="real transport failure"):
            await call_tool_with_firewall(db_session, org_id, user_id, server, "search", {})

    assert mock_log_audit.call_args.kwargs["success"] is False
    assert "real transport failure" in mock_log_audit.call_args.kwargs["failure_reason"]
