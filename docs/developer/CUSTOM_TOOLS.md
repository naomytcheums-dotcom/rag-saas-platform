# Tools & Function Calling

## The real function-calling loop

`AgentOrchestrator.run_agent` (`api/services/agent_orchestrator.py`)
runs a real, provider-native function-calling loop: tool schemas are
sent to the LLM as `tools=[...]`, `message.tool_calls` is parsed,
each real tool handler is awaited, and its result is fed back as a
`role:"tool"` message — looped up to `AGENT_MAX_TOOL_ITERATIONS` (8 by
default), with an honest error if that cap is hit rather than an
infinite loop. Multiple tool calls in the same turn run concurrently
(`asyncio.gather`), each under its own timeout
(`AGENT_TOOL_CALL_TIMEOUT`). Every call is recorded as an `AgentTrace`
row (`step_type="tool_call"`), with secrets redacted before storage.

## Where a tool comes from

An agent's own `tools` list can reference three real kinds of tools,
all resolved by `api/services/agent_tools.py`'s own
`resolve_agent_tools`:

1. **Built-in tools** (`api/services/tools.py`'s own registry):
   `calculator`, `word_count`, `github_get_repo`, `github_list_issues`,
   `calendar_list_events`, `calendar_create_event`, `email_read`,
   `http_request` (SSRF-protected), plus `execute_sql_query` (built
   fresh per run, with `organization_id` bound by closure so an LLM's
   own tool-call arguments can never target a different organization).
2. **Custom tools** (this doc, below) — an organization's own webhook
   tools.
3. **MCP tools** — an external MCP server's tools, referenced as
   `mcp:{server_id}:{tool_name}`. See
   [`docs/mcp/CLIENT.md`](../mcp/CLIENT.md).

## Cross-run memory

Beyond the existing per-session short-term memory, a tool (or an
explicit API call) can write a fact that outlives one conversation via
`AgentLongTermMemoryItem` (`GET/PUT/DELETE /agents/{agent_id}/memory[/{key}]`)
— org-wide (`user_id` null) or per-user, read automatically at the
start of every run.

## Custom tools (org-defined webhooks)

Custom tools extend what an [agent](../user/AGENTS.md) or
[autonomous agent](../advanced/AUTONOMOUS_AGENTS.md) can do beyond
built-in retrieval/generation — `api/routers/custom_tools.py`,
`api/routers/tool_config.py`, `api/routers/tool_permissions.py`.

## Defining a tool

A tool declares a name, a description (used for tool selection — see
[`docs/autonomous/EXECUTION.md`](../autonomous/EXECUTION.md) for how
autonomous agents rank and pick tools), a parameter schema, and an
execution target (an HTTP endpoint you control, or a built-in handler).

## Assigning tools to an agent

Attach a tool to an agent's configuration under **Admin → Agents →
[agent] → Tools**. An agent only has access to the tools explicitly
assigned to it.

## Tool permissions

`tool_permissions.py` controls which roles/members can configure or
invoke a given tool, separate from the agent-level tool assignment
above.

## Guardrails

Autonomous agent tool use is additionally subject to guardrails
(content filtering, cost limits) — see
[`docs/autonomous/OVERVIEW.md`](../autonomous/OVERVIEW.md).
