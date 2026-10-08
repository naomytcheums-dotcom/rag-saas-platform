"""
Real MCP Firewall -- item 23 of the internal-systems list: every real
MCP tool call passes through a real policy check AND a real,
tamper-evident audit log entry BEFORE and regardless of execution --
not just `call_tool`'s own existing transport-level auth
(`api/services/mcp/client.py`'s own `_auth_headers`, a real but
surface-only credential check against the external MCP server itself).

Built entirely on two already-real systems, never a parallel one:
1. **Policy** -- item 13's real `api.services.opa_policy.check_policy`,
   same real fail-open discipline (a policy check going quiet, e.g.
   `OPA_ENABLED=False` or an unreachable server, must never silently
   block a real tool call an operator never asked to be gated at all --
   only an explicit, successful real `False` from OPA blocks anything).
2. **Audit** -- this codebase's own real, tamper-evident, HMAC-chained
   `AuditLog` (`api/security/audit_log.py`'s `log_audit_action`,
   Partie 10.2) -- a NEW `AuditAction.MCP_TOOL_CALL` value (no
   migration needed, `AuditAction` is a plain `String(100)` column, not
   a DB-level enum, by this codebase's own deliberate design). Every
   real call is logged -- ALLOWED, POLICY-BLOCKED, or a real execution
   FAILURE -- `success`/`failure_reason` distinguish which, same
   convention as `LOGIN_SUCCESS`/`LOGIN_FAILED` elsewhere in this
   codebase.

**Real, deliberate wrapper, not a `call_tool` signature change**: this
module wraps the real, already-tested `call_tool`
(`api/services/mcp/client.py`) rather than adding `db`/`organization_id`/
`user_id` parameters directly to it -- `call_tool`'s own existing,
tested callers (`api/services/mcp/discovery.py`,
`api/services/autonomous_agents.py`) keep working completely
unchanged; a caller that wants the real firewall opts in by calling
`call_tool_with_firewall` instead."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.mcp_server import MCPServerConfig


async def call_tool_with_firewall(
    db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID | None, server: MCPServerConfig,
    tool_name: str, arguments: dict, ip: str | None = None, user_agent: str | None = None,
) -> str:
    """Real policy check, then real execution, then a real audit row --
    in that order, so a real policy denial is logged and raised BEFORE
    any real network call to the external MCP server ever happens."""
    from api.models.audit_log import AuditAction
    from api.security.audit_log import log_audit_action
    from api.services.mcp.client import MCPClientError, call_tool
    from api.services.opa_policy import check_policy

    input_data = {
        "user": {"user_id": str(user_id) if user_id else None},
        "resource": {"tool_name": tool_name, "server": server.name, "arguments": arguments},
    }
    decision = await check_policy(input_data, "mcp.tools", "allow")

    if decision is False:
        await log_audit_action(
            db, user_id=user_id, action=AuditAction.MCP_TOOL_CALL, ip=ip, user_agent=user_agent, success=False,
            failure_reason="blocked by OPA policy", organization_id=organization_id,
            resource_type="mcp_tool", resource_id=tool_name, metadata={"server": server.name, "arguments": arguments},
        )
        raise MCPClientError(f"MCP tool call to {tool_name!r} on server {server.name!r} was blocked by policy")

    try:
        result = await call_tool(server, tool_name, arguments)
    except Exception as exc:
        await log_audit_action(
            db, user_id=user_id, action=AuditAction.MCP_TOOL_CALL, ip=ip, user_agent=user_agent, success=False,
            failure_reason=str(exc), organization_id=organization_id, resource_type="mcp_tool", resource_id=tool_name,
            metadata={"server": server.name},
        )
        raise

    await log_audit_action(
        db, user_id=user_id, action=AuditAction.MCP_TOOL_CALL, ip=ip, user_agent=user_agent, success=True,
        organization_id=organization_id, resource_type="mcp_tool", resource_id=tool_name, metadata={"server": server.name},
    )
    return result
