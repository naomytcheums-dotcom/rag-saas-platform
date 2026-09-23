# MCP Client

Lets your organization's agents call tools exposed by an external MCP
server. Real, org-scoped, Admin+-managed.

## Registering a server

```bash
curl -X POST https://your-instance/organizations/{org_id}/mcp-servers \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "GitHub MCP",
    "transport": "streamable_http",
    "url": "https://mcp.example.com/github",
    "auth_type": "bearer",
    "auth_credential": "ghp_..."
  }'
```

`transport` is one of `stdio`, `sse`, `streamable_http`. `stdio` needs
`command`/`args`/`env` instead of `url` — a real, local subprocess this
platform's own host runs, so only configure it with a command you trust
(same trust boundary as a custom webhook tool's URL, just for a local
binary instead of a remote call).

`auth_credential` (bearer token or API key) is encrypted at rest
(`api/security/encryption.py`) and never returned by any `GET`.

## Discovering tools

```bash
curl -X POST https://your-instance/organizations/{org_id}/mcp-servers/{server_id}/sync \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Runs a real `tools/list` against the server and caches the result
(`GET .../mcp-servers/{server_id}/tools` to read it back). `test`
(`POST .../mcp-servers/{server_id}/test`) does the same round-trip
without persisting, for a quick "is this server reachable" check.

## Using an MCP tool in an agent

Add an entry to the agent's own `tools` list with the name
`mcp:{server_id}:{tool_name}` (the exact tool name from a `sync`).
`AgentOrchestrator`'s real function-calling loop resolves it exactly
like a built-in tool — the LLM never knows the difference.

## Calling a tool directly

```bash
curl -X POST https://your-instance/organizations/{org_id}/mcp-servers/{server_id}/tools/{tool_name}/call \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{"arguments": {"owner": "anthropics", "repo": "mcp"}}'
```
