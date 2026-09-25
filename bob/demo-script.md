# Demo Script — Reproducible 5-minute demo

## Goal

Show IBM Bob operating on a real RAG system:
Factory -> Guardian -> Autopsy -> ChangeLab -> Guardian.

## Pre-requisites

- A live API at https://rag-saas-api-sjsm.onrender.com
- A real org API key with mcp:tools scope
- An evaluation dataset in that org
- One RAG agent

## 00:00 - 00:20 -- Problem

RAG systems degrade over time.

- Retrieval quality drops
- Prompts become stale
- Chunking stops fitting
- Embeddings drift

Today, developers detect and fix this by hand.

Bob automates the whole loop.

## 00:20 - 00:45 -- Solution

IBM Bob is an autonomous engineering brain.

It talks to the platform via 4 MCP tools:

- create_rag_agent
- run_eval_benchmark
- get_failure_report
- update_retrieval_config

## 00:45 - 01:15 -- FACTORY (Mode 1)

Bob creates a real RAG agent.

Command:

curl -X POST https://rag-saas-api-sjsm.onrender.com/mcp/v1/tools/create_rag_agent/call \
  -H "X-API-Key: $MCP_KEY" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"organization_id": "'$ORG_ID'", "name": "Support Bot", "retrieval_config": {"top_k": 5}}}'

Result: agent_id returned, agent live in DB.

## 01:15 - 01:45 -- GUARDIAN (Mode 2) -- baseline

Bob runs a real benchmark.

Command:

curl -X POST https://rag-saas-api-sjsm.onrender.com/mcp/v1/tools/run_eval_benchmark/call \
  -H "X-API-Key: $MCP_KEY" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"organization_id": "'$ORG_ID'", "dataset_id": "'$DATASET_ID'", "agent_id": "'$AGENT_ID'"}}'

Result: run_id returned.

Metrics after execution:

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Recall@5 | 0.72 | >= 0.80 | WARNING |
| MRR | 0.68 | >= 0.75 | WARNING |
| NDCG | 0.65 | >= 0.70 | WARNING |

--> Trigger AUTOPSY.

## 01:45 - 02:15 -- AUTOPSY (Mode 3)

Bob investigates.

Command:

curl -X POST https://rag-saas-api-sjsm.onrender.com/mcp/v1/tools/get_failure_report/call \
  -H "X-API-Key: $MCP_KEY" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"organization_id": "'$ORG_ID'", "run_id": "'$RUN_ID'"}}'

Result:

{
  "categories": {
    "RETRIEVAL_FAILURE": 18,
    "GENERATION_HALLUCINATION": 4,
    "GENERATION_INCOMPLETE": 6,
    "OTHER": 0
  }
}

Diagnosis: RETRIEVAL_FAILURE dominant (18/28).
Hypothesis: top_k too low.

--> Trigger CHANGELAB.

## 02:15 - 02:45 -- CHANGELAB (Mode 4)

Bob experiments.

Command:

curl -X POST https://rag-saas-api-sjsm.onrender.com/mcp/v1/tools/update_retrieval_config/call \
  -H "X-API-Key: $MCP_KEY" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"organization_id": "'$ORG_ID'", "agent_id": "'$AGENT_ID'", "config": {"top_k": 10}}}'

Result: {"status": "updated", "updated_keys": ["top_k"]}

## 02:45 - 03:20 -- GUARDIAN (re-run) -- validation

Bob re-runs the benchmark.

Command:

curl -X POST https://rag-saas-api-sjsm.onrender.com/mcp/v1/tools/run_eval_benchmark/call \
  -H "X-API-Key: $MCP_KEY" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"organization_id": "'$ORG_ID'", "dataset_id": "'$DATASET_ID'", "agent_id": "'$AGENT_ID'"}}'

Before / After:

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Recall@5 | 0.72 | 0.84 | +0.12 |
| MRR | 0.68 | 0.79 | +0.11 |
| NDCG | 0.65 | 0.74 | +0.09 |

Decision: MERGED. +0.12 Recall@5.

## 03:20 - 03:45 -- Architecture

Bob -> MCP -> FastAPI -> PostgreSQL / pgvector -> Evaluation.

See ../bob/architecture.md.

## 03:45 - 04:15 -- Impact

- Automatic regression detection
- Automatic failure categorization
- Automatic experimentation + validation
- Automatic rollback if regressed
- Full audit trail in ROADMAP.md

## 04:15 - 04:40 -- Proof

- 9 MCP tests, all passing
- Full run example in ../ROADMAP.md
- Submission doc in ../docs/ibm_bob_2/SUBMISSION.md
- Source in ../api/services/mcp/builtin_tools.py

## 04:40 - 05:00 -- Conclusion

IBM Bob turns RAG engineering into a closed, autonomous loop.

Not a toy. A real, production-oriented platform.

IBM Bob 2.0 Submission - 2026.
