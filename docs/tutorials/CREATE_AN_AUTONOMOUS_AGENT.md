# Tutorial: Create an Autonomous Agent

See [Autonomous Agents](../advanced/AUTONOMOUS_AGENTS.md) first for the
concept — this walks through creating and running one.

## 1. Create the agent

```bash
curl -X POST "https://your-instance.example.com/organizations/$ORG_ID/autonomous-agents" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "name": "Competitor Research Agent",
    "goal_template": "Research {competitor} and summarize their pricing",
    "max_steps": 10,
    "allowed_tools": ["web_search", "document_search"]
  }'
```

## 2. Run it

```bash
curl -X POST "https://your-instance.example.com/autonomous-agents/$AGENT_ID/run" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"goal": "Research Acme Corp and summarize their pricing"}'
```

Returns a plan ID. The agent plans its steps, then executes them one at
a time.

## 3. Track progress

```bash
curl "https://your-instance.example.com/autonomous-agents/$AGENT_ID/plans/$PLAN_ID" \
  -H "Authorization: Bearer $API_KEY"
```

Each step shows its status (`pending`, `running`, `completed`,
`failed`, `paused`). A run pauses automatically if it hits `max_steps`
or the configured cost ceiling — see
[Quotas & Limits](../admin/QUOTAS_AND_LIMITS.md#autonomous-agent-cost-limits).
Pause or stop a run explicitly with
`POST /autonomous-agents/{agent_id}/pause` or `.../stop`.

## 4. Check cost

```bash
curl "https://your-instance.example.com/autonomous-agents/$AGENT_ID/cost" \
  -H "Authorization: Bearer $API_KEY"
```

See [`docs/autonomous/EXECUTION.md`](../autonomous/EXECUTION.md) for
what happens step by step under the hood.
