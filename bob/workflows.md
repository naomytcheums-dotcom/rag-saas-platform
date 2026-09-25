# Workflows — The closed loop

## The full loop

IBM BOB 2.0
    |
    v
FACTORY --> GUARDIAN --> AUTOPSY --> CHANGELAB
    ^                                    |
    |                                    v
    |                             tests + benchmark
    |                                    |
    |                                    v
    |                           KEEP / ROLLBACK
    |                                    |
    +------------------------------------+
                  GUARDIAN

## Mode 1 — FACTORY

Goal: provision a real RAG agent.

Steps:
1. Bob reads a requirement.
2. Bob calls create_rag_agent.
3. Agent is created in DB with retrieval_config.

MCP call:

POST /mcp/v1/tools/create_rag_agent/call

{
  "arguments": {
    "organization_id": "org-uuid",
    "name": "Support Bot",
    "model": "claude-3-5-sonnet",
    "retrieval_config": {"strategy": "hybrid", "top_k": 5}
  }
}

Response: {"agent_id": "...", "status": "created"}

## Mode 2 — GUARDIAN

Goal: measure real quality.

Steps:
1. Bob calls run_eval_benchmark.
2. The job runs against a dataset.
3. Real metrics computed: Recall@1/3/5/10, MRR, NDCG, hallucination rate, latency, tokens, cost.

MCP call:

POST /mcp/v1/tools/run_eval_benchmark/call

{
  "arguments": {
    "organization_id": "org-uuid",
    "dataset_id": "dataset-uuid",
    "agent_id": "agent-uuid"
  }
}

Response: {"run_id": "...", "status": "queued"}

Threshold check:

| Metric | Warning | Critical |
|--------|---------|----------|
| Recall@5 | < 0.80 | < 0.70 |
| Recall@10 | < 0.85 | < 0.75 |
| MRR | < 0.75 | < 0.65 |
| NDCG | < 0.70 | < 0.60 |
| Hallucination rate | > 0.10 | > 0.20 |

If warning or critical, go to Mode 3.

## Mode 3 — AUTOPSY

Goal: find the root cause.

Steps:
1. Bob calls get_failure_report.
2. Each failure is categorized.
3. Bob reads the dominant category.

MCP call:

POST /mcp/v1/tools/get_failure_report/call

{
  "arguments": {
    "organization_id": "org-uuid",
    "run_id": "run-uuid"
  }
}

Response:

{
  "failures": ["..."],
  "categories": {
    "RETRIEVAL_FAILURE": 18,
    "GENERATION_HALLUCINATION": 4,
    "GENERATION_INCOMPLETE": 6,
    "OTHER": 0
  }
}

Hypothesis examples:
- RETRIEVAL_FAILURE dominant -> top_k too low
- GENERATION_HALLUCINATION dominant -> prompt needs stricter grounding
- GENERATION_INCOMPLETE dominant -> max_tokens too low

## Mode 4 — CHANGELAB

Goal: fix it and prove it.

Steps:
1. Bob calls update_retrieval_config (targeted change).
2. Bob re-runs run_eval_benchmark.
3. Bob compares baseline vs new.
4. If improved, keep. If regressed, rollback.

MCP call:

POST /mcp/v1/tools/update_retrieval_config/call

{
  "arguments": {
    "organization_id": "org-uuid",
    "agent_id": "agent-uuid",
    "config": {"top_k": 10}
  }
}

Response: {"status": "updated", "updated_keys": ["top_k"]}

Decision:

if new_recall > baseline_recall:  KEEP
else:                             ROLLBACK

## The full chain — real example

GUARDIAN   Recall@5 = 0.72  (WARNING)
AUTOPSY    RETRIEVAL_FAILURE dominant (18/28)
CHANGELAB  top_k 5 -> 10
GUARDIAN   Recall@5 = 0.84  (MERGED, +0.12)

Full example: ../ROADMAP.md under [Bob-Auto-Fixes].
