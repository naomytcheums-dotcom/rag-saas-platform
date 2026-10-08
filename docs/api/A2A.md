# A2A (Agent2Agent)

Each organization can expose its RAG agent to external A2A-compliant agents. Authentication is an
organization API key carrying the `a2a:call` scope (`X-API-Key`). The organization in the path must be the
key's own organization — anything else is a `404`.

```
GET  /a2a/{org_id}/.well-known/agent-card.json     # discovery (agent card)
POST /a2a/{org_id}                                 # A2A JSON-RPC (e.g. method "SendMessage"), header A2A-Version: 1.0
```

Scope of the implementation: non-streaming, no push notifications, task state kept in memory per request
(the agent card advertises exactly that).

Cost control: each task passes the organization's rate limit (`ratelimit:a2a:org:*`), a pre-flight credit /
daily-monthly spend-cap check (BYOK organizations are exempt) and is then debited a flat
`A2A_TASK_CREDIT_COST` — an estimate, because the underlying agent does not expose token usage.
Errors before the task starts: `402` insufficient credits, `429` rate limit or spend cap.
