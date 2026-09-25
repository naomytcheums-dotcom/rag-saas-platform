# MCP Tools — The 4 tools exposed to IBM Bob

## Overview

Bob talks to the platform via 4 MCP tools, exposed at:

GET  /mcp/v1/tools              -- list the tools
POST /mcp/v1/tools/{name}/call  -- execute a tool

Auth: X-API-Key header with mcp:tools scope.

## Tool 1 — create_rag_agent

Mode: FACTORY (Mode 1)

Purpose: provision a real, multi-tenant RAG agent.

Underlying service: api/models/agent.py (Agent model)

Input schema:

{
  "organization_id": "uuid (required)",
  "name": "string (required)",
  "model": "string (optional, default claude-3-5-sonnet)",
  "system_prompt": "string (optional)",
  "retrieval_config": "object (optional)"
}

Output:

{"agent_id": "uuid", "status": "created"}

Errors:
- MCPBuiltinToolError if name missing
- MCPBuiltinToolError if organization_id invalid

## Tool 2 — run_eval_benchmark

Mode: GUARDIAN (Mode 2) + CHANGELAB (Mode 4)

Purpose: launch a real benchmark against a dataset.

Underlying service: api/services/evaluation_jobs.py (create_job)

Input schema:

{
  "organization_id": "uuid (required)",
  "dataset_id": "uuid (required)",
  "agent_id": "uuid (optional)",
  "config": "object (optional)"
}

Output:

{"run_id": "uuid", "status": "queued"}

Metrics computed after execution:
- Recall@1, Recall@3, Recall@5, Recall@10
- MRR (Mean Reciprocal Rank)
- NDCG
- Hallucination rate
- Latency
- Tokens
- Cost

## Tool 3 — get_failure_report

Mode: AUTOPSY (Mode 3)

Purpose: categorize a real evaluation run's failures.

Underlying service: api/models/evaluation.py (EvaluationFailure rows)

Input schema:

{
  "organization_id": "uuid (required)",
  "run_id": "uuid (required)"
}

Output:

{
  "failures": [
    {"question": "...", "category": "...", "expected": "...", "actual": "..."}
  ],
  "categories": {
    "RETRIEVAL_FAILURE": 18,
    "GENERATION_HALLUCINATION": 4,
    "GENERATION_INCOMPLETE": 6,
    "OTHER": 0
  }
}

Failure categories:
- RETRIEVAL_FAILURE -- expected documents not retrieved
- GENERATION_HALLUCINATION -- context retrieved but answer hallucinated
- GENERATION_INCOMPLETE -- answer truncated or partial
- OTHER

## Tool 4 — update_retrieval_config

Mode: CHANGELAB (Mode 4)

Purpose: partial-update an agent's retrieval_config.

Underlying service: api/models/agent.py (Agent.knowledge_base_config)

Input schema:

{
  "organization_id": "uuid (required)",
  "agent_id": "uuid (required)",
  "config": "object (required, non-empty)"
}

Output:

{"status": "updated", "updated_keys": ["top_k"]}

Behavior:
- Real merge, not replacement
- A targeted change (e.g. top_k 5 -> 10) does not wipe other keys

Enables A/B auto-tuning:
1. Baseline benchmark
2. Update config
3. Re-benchmark
4. If improved, keep. If regressed, rollback.

## List the tools

GET /mcp/v1/tools
X-API-Key: <key>

Response:
{
  "tools": [
    {"name": "create_rag_agent", "description": "...", "input_schema": {...}},
    {"name": "get_failure_report", "description": "...", "input_schema": {...}},
    {"name": "update_retrieval_config", "description": "...", "input_schema": {...}},
    {"name": "run_eval_benchmark", "description": "...", "input_schema": {...}}
  ]
}

## Source code

| File | Role |
|------|------|
| api/services/mcp/builtin_tools.py | The 4 tools |
| api/routers/mcp_server.py | The MCP routes |
| tests/test_mcp_builtin_tools.py | 9 tests, all passing |
