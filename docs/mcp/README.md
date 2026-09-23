# MCP (Model Context Protocol)

Phase 5, Étape 9 — real support for both directions of MCP:

- **[CLIENT.md](CLIENT.md)** — this platform's own agents calling tools
  exposed by an external MCP server you register.
- **[SERVER.md](SERVER.md)** — external MCP clients (Claude Desktop,
  another agent platform, ...) calling this platform's own tools.
- **[TOOLS.md](TOOLS.md)** — how an MCP-sourced tool shows up next to
  this platform's own built-in tools, on either side.

## Why both directions

An MCP-aware SaaS is a two-way door: your own agents should be able to
reach tools you don't have to build yourself (a GitHub MCP server, a
Postgres MCP server, ...), and external MCP clients should be able to
reach the tools this platform already has (RAG search, workflow
triggers, ...) without a bespoke integration per client. Both are real
here, built on Anthropic's own official `mcp` Python SDK — no
hand-rolled JSON-RPC.

## Scope of this étape

Real and shipped: MCP client (stdio/sse/streamable_http transports,
tool discovery + calling, integrated into agent tool resolution), MCP
server (exposes the static, built-in tool registry over a real
`tools/list`/`tools/call` HTTP surface, org-scoped `X-API-Key` auth).

Traced, not built here: custom org-defined webhook tools and per-run
tools (like the SQL query tool) are not yet exposed via the MCP server
role — see the project ROADMAP for why and the concrete plan.
