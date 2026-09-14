# Custom Tools

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
