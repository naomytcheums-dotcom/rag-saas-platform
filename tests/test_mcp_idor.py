"""P2C-7: foreign MCP client rows and MCP server API-key resource binding."""

from unittest.mock import AsyncMock

from api.models.agent import Agent
from api.models.mcp_server import MCPServerConfig, MCPToolCache
from test_document_idor import denied, make_key, make_tenants, snapshot


async def test_mcp_idor(client, db_session, monkeypatch):
    (owner, org_a, _), (attacker, org_b, _) = await make_tenants(
        client, db_session, monkeypatch, "mcp"
    )
    server = MCPServerConfig(
        organization_id=org_a, name="private-server", transport="streamable_http",
        url="https://p2c.invalid/mcp",
    )
    agent = Agent(
        organization_id=org_a, name="private-agent", system_prompt="private-prompt",
        model_config_json={}, knowledge_base_config={"top_k": 5},
    )
    db_session.add_all([server, agent])
    await db_session.flush()
    tool = MCPToolCache(server_id=server.id, name="private-tool", input_schema={})
    db_session.add(tool)
    await db_session.commit()
    server_id, agent_id = server.id, agent.id
    baseline = await snapshot(db_session, server, tool, agent)
    connection, sync, call = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr("api.routers.mcp_servers.test_connection", connection)
    monkeypatch.setattr("api.routers.mcp_servers.sync_tools", sync)
    monkeypatch.setattr("api.routers.mcp_servers.call_cached_tool", call)
    control = await client.get(
        f"/organizations/{org_a}/mcp-servers/{server_id}/tools", headers=owner
    )
    assert control.status_code == 200, control.text
    assert control.json()[0]["name"] == "private-tool"
    violations = []
    await denied(client, "GET", f"/organizations/{org_a}/mcp-servers", attacker, violations)
    for path_org in (org_a, org_b):
        root = f"/organizations/{path_org}/mcp-servers/{server_id}"
        await denied(client, "GET", root + "/tools", attacker, violations)
        await denied(
            client, "PATCH", root, attacker, violations, json={"name": "attacker-rename"}
        )
        for action in ("test", "sync"):
            await denied(client, "POST", root + "/" + action, attacker, violations)
        await denied(
            client, "POST", root + "/tools/private-tool/call", attacker, violations,
            json={"arguments": {}},
        )
        await denied(client, "DELETE", root, attacker, violations)
    key = await make_key(client, attacker, org_b, ["mcp:tools"])
    path = "/mcp/v1/tools/update_retrieval_config/call"
    await denied(
        client, "POST", path, key, violations,
        json={"organization_id": str(org_a), "agent_id": str(agent_id), "config": {"top_k": 10}},
    )
    logical_denial = await denied(
        client, "POST", path, key, violations, expected=(200,),
        json={"agent_id": str(agent_id), "config": {"top_k": 10}},
    )
    body = logical_denial.json()
    if body.get("is_error") is not True or "Agent not found" not in logical_denial.text:
        violations.append("MCP logical denial missing for a real foreign agent")
    assert await snapshot(db_session, server, tool, agent) == baseline
    for boundary in (connection, sync, call):
        boundary.assert_not_called()
    assert not violations, "\n".join(violations)
