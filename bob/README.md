# IBM Bob 2.0 — RAG Evolution Factory

**An IBM Bob-powered autonomous engineering system that creates, evaluates, diagnoses and improves RAG agents through a closed-loop workflow.**

---

## What this directory contains

This `bob/` directory is the **competition-focused entry point** for the IBM Bob 2.0 submission.

| File | Purpose |
|------|---------|
| [README.md](README.md) | This file — overview |
| [architecture.md](architecture.md) | How IBM Bob interacts with the platform |
| [workflows.md](workflows.md) | The closed-loop workflow (4 modes) |
| [mcp-tools.md](mcp-tools.md) | The 4 MCP tools exposed to Bob |
| [demo-script.md](demo-script.md) | Reproducible 5-minute demo script |

---

## The problem Bob solves

RAG systems degrade over time.

- Retrieval quality drops as documents change
- Prompts become stale
- Chunking strategies stop fitting the data
- Embeddings drift

**Today, developers have to manually:**
- Detect the regression
- Diagnose the root cause
- Try a fix
- Measure whether it worked
- Roll back if it didn't

**IBM Bob automates this entire loop.**

---

## The 4 modes

| Mode | MCP Tool | What Bob does |
|------|----------|---------------|
| **1 — FACTORY** | `create_rag_agent` | Provision a real multi-tenant RAG agent |
| **2 — GUARDIAN** | `run_eval_benchmark` | Monitor real metrics (Recall@K, MRR, NDCG, hallucination) |
| **3 — AUTOPSY** | `get_failure_report` | Investigate and categorize failures |
| **4 — CHANGELAB** | `update_retrieval_config` | Experiment, re-benchmark, keep or roll back |

---

## The closed loop
IBM BOB 2.0
│
▼
FACTORY ──► GUARDIAN ──► AUTOPSY ──► CHANGELAB
▲ │
│ ▼
│ tests + benchmark
│ │
│ ▼
└──────────────── KEEP / ROLLBACK

text

---

## Real environment

Bob operates on the **real RAG SaaS platform** in this repository:

- 89 API routers
- 314 backend test files
- 52 RBAC permissions
- 36 CRM connectors
- 6 i18n languages (~4,200 translations)

This is **not a toy project** — Bob works on a real, complex production-grade system.

---

## Proof

| Evidence | Location |
|----------|----------|
| The 4 MCP tools | [../api/services/mcp/builtin_tools.py](../api/services/mcp/builtin_tools.py) |
| The 9 tests | [../tests/test_mcp_builtin_tools.py](../tests/test_mcp_builtin_tools.py) |
| Full run example | [../ROADMAP.md](../ROADMAP.md) under `[Bob-Auto-Fixes]` |
| Submission document | [../docs/ibm_bob_2/SUBMISSION.md](../docs/ibm_bob_2/SUBMISSION.md) |
| The contract | [../agents.md](../agents.md) |

---

**IBM Bob 2.0 Submission — 2026**
