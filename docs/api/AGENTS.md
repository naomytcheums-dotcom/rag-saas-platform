# Agents API

Two distinct resources — see
[Autonomous Agents](../advanced/AUTONOMOUS_AGENTS.md) for the
architectural difference.

## Configured agents (`api/routers/agents.py`)

```
GET  /organizations/{org_id}/agents
POST /organizations/{org_id}/agents
```

An agent resource has a system prompt, model config, and an assigned
tool set — see [Custom Tools](../developer/CUSTOM_TOOLS.md). Per-tool
permissions are managed separately:

```
GET    /organizations/{org_id}/agents/{agent_id}/tools/permissions
POST   /organizations/{org_id}/agents/{agent_id}/tools/{tool_name}/permissions
DELETE /organizations/{org_id}/agents/{agent_id}/tools/{tool_name}/permissions/{user_id}
```

Agent run traces (step-by-step execution history) are available under:

```
GET /organizations/{org_id}/agents/runs/{run_id}/traces
GET /organizations/{org_id}/agents/runs/{run_id}/traces/tree
GET /organizations/{org_id}/agents/runs/{run_id}/traces/export
```

## Public API

A simpler, versioned surface is also available for external
integrations:

```
GET  /v1/agents
POST /v1/agents/run
```

## Autonomous agents (`api/routers/autonomous_agents.py`)

Creation is organization-scoped; everything else operates on the agent
directly by id:

```
GET/POST /organizations/{org_id}/autonomous-agents
GET/PATCH/DELETE /autonomous-agents/{agent_id}

POST /autonomous-agents/{agent_id}/run
POST /autonomous-agents/{agent_id}/pause
POST /autonomous-agents/{agent_id}/resume
POST /autonomous-agents/{agent_id}/stop
GET  /autonomous-agents/{agent_id}/status

GET  /autonomous-agents/{agent_id}/plans
GET  /autonomous-agents/{agent_id}/plans/{plan_id}
GET  /autonomous-agents/{agent_id}/plans/{plan_id}/steps

GET/POST /autonomous-agents/{agent_id}/memory
DELETE   /autonomous-agents/{agent_id}/memory/{memory_id}

POST /autonomous-agents/{agent_id}/collaborate
GET  /autonomous-agents/{agent_id}/collaborations

GET  /autonomous-agents/{agent_id}/cost
```

Running an autonomous agent creates an `AgentPlan` with `AgentStep`s,
executed asynchronously — poll the plan or listen for a webhook event
for step-by-step progress. See
[`docs/autonomous/EXECUTION.md`](../autonomous/EXECUTION.md) and
[`docs/autonomous/OVERVIEW.md`](../autonomous/OVERVIEW.md) for the full
memory, collaboration, and cost-tracking behavior.

## API keys for agent access

Agents/autonomous agents accessed programmatically (rather than through
the dashboard) authenticate the same way as any other API consumer —
see [Authentication](AUTHENTICATION.md) and
`api/routers/agent_api_keys.py`.
