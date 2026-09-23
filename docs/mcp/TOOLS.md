# MCP Tools

## Client side (external tools reaching your agents)

Once a server is registered and synced (see [CLIENT.md](CLIENT.md)),
its tools appear via `GET /organizations/{org_id}/mcp-servers/{server_id}/tools`,
each named exactly as the external server named it. To let an agent
actually call one, add `mcp:{server_id}:{tool_name}` to that agent's
own `tools` list (`PUT /agents/{agent_id}/tools`) — no different from
enabling a built-in tool.

`AgentOrchestrator.run_agent`'s real function-calling loop resolves
these per-run (`api/services/agent_tools.py`'s own `_build_mcp_tool`):
the server's own encrypted credentials are decrypted only for that
one call, never exposed to the LLM.

## Server side (your tools reaching external clients)

`GET /mcp/v1/tools` (see [SERVER.md](SERVER.md)) returns this
platform's own static tool registry (`api/services/tools.py`) in a
real, MCP-shaped `input_schema` per tool — an external client (Claude
Desktop, another agent framework) can drive them exactly like any other
MCP server's tools, no platform-specific glue code on their side.

## What's NOT exposed either direction (yet)

Custom, per-organization webhook tools
(`api/models/custom_tool.py`) and per-run tools bound to
`db`/`organization_id` by closure (`execute_sql_query`) are real and
usable inside this platform's own agents, but not yet reachable through
either MCP direction — see the project ROADMAP for the concrete,
traced plan.
