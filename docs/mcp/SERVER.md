# MCP Server

Exposes this platform's own built-in tool registry to external MCP
clients (Claude Desktop, another agent platform, a script using the
`mcp` SDK's own client) over a real, wire-compatible HTTP surface.

## Authentication

Reuses this platform's existing organization API keys — no new auth
mechanism. Create a key with the `mcp:tools` scope:

```bash
curl -X POST https://your-instance/organizations/{org_id}/api-keys \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "MCP client", "scopes": ["mcp:tools"]}'
```

Every call to `/mcp/v1/*` below gets the same rate-limiting and quota
enforcement as every other public `/v1/*`-style endpoint, for free,
just by depending on the same `require_public_api_scope("mcp:tools")`.

## Endpoints

```
GET  /mcp/v1/tools                     -> {"tools": [{"name", "description", "input_schema"}, ...]}
POST /mcp/v1/tools/{tool_name}/call    -> {"content": [{"type": "text", "text": ...}], "is_error": bool}
```

Both header names and body shapes match `mcp.types.ListToolsResult`/
`CallToolResult`'s own real field names from Anthropic's official SDK
(verified against the installed `mcp` package, not guessed).

```bash
curl https://your-instance/mcp/v1/tools -H "X-API-Key: $YOUR_KEY"

curl -X POST https://your-instance/mcp/v1/tools/calculator/call \
  -H "X-API-Key: $YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"arguments": {"expression": "2 + 2"}}'
```

## What's exposed

Only the static, built-in tool registry (`calculator`, `word_count`,
`github_get_repo`, `github_list_issues`, `calendar_list_events`,
`calendar_create_event`, `email_read`, `http_request`) — not this
organization's own custom webhook tools or per-run tools like the SQL
query tool, which need a real per-tool review before being exposed
generically to an external caller. Traced in the project ROADMAP.
