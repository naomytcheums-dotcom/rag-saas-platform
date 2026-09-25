# IBM Bob 2.0 — Submission

## Project: RAG SaaS Platform

- **Live demo**: https://rag-saas-platform-rho.vercel.app
- **Live API**: https://rag-saas-api-sjsm.onrender.com
- **Repository**: https://github.com/naomytcheums-dotcom/rag-saas-platform
- **Contract**: `agents.md` — 10 sections, 100% implemented

---

## 1. Executive Summary

RAG SaaS Platform is a multi-tenant, production-oriented RAG SaaS platform built across 25 documented development parts.

For the IBM Bob 2.0 track, the platform implements and exposes the 4 operational modes named in the `agents.md` contract as real MCP tools, callable by any external MCP client over HTTP.

---

## 2. Key numbers

| Metric | Value |
|--------|-------|
| API routers | 89 |
| Frontend sections | 17 |
| Backend test files | 314 |
| i18n languages | 6 (EN, FR, ES, DE, PT, AR) |
| Translations | ~4,200 keys |
| RBAC permissions | 52 |
| CRM connectors | 36 |
| IBM Bob 2.0 modes | 4 (all implemented) |
| MCP tools (Bob) | 4 |

---

## 3. The 4 modes (agents.md contract)

### Mode 1 — FACTORY

- **MCP tool**: `create_rag_agent`
- **Underlying service**: `api/models/agent.py`
- **HTTP**: `POST /mcp/v1/tools/create_rag_agent/call`

Provisions a real, multi-tenant RAG agent with organization_id, name, system_prompt, model_config_json, knowledge_base_config.

Returns: `{"agent_id": "...", "status": "created"}`

### Mode 2 — GUARDIAN

- **MCP tool**: `run_eval_benchmark`
- **Underlying service**: `api/services/evaluation_jobs.py`
- **HTTP**: `POST /mcp/v1/tools/run_eval_benchmark/call`

Launches a real evaluation benchmark against a dataset, producing real per-question metrics: Recall@1/3/5/10, MRR, NDCG, hallucination rate, latency, token usage, cost.

Returns: `{"run_id": "...", "status": "queued"}`

### Mode 3 — AUTOPSY

- **MCP tool**: `get_failure_report`
- **Underlying service**: `api/models/evaluation.py`
- **HTTP**: `POST /mcp/v1/tools/get_failure_report/call`

Categorizes a real evaluation run's failures into: RETRIEVAL_FAILURE, GENERATION_HALLUCINATION, GENERATION_INCOMPLETE, OTHER.

Returns: `{"failures": [...], "categories": {...}}`

### Mode 4 — CHANGELAB

- **MCP tool**: `update_retrieval_config`
- **Underlying service**: `api/models/agent.py`
- **HTTP**: `POST /mcp/v1/tools/update_retrieval_config/call`

Partial-updates an agent's retrieval_config (real merge, not replacement). Combined with run_eval_benchmark, this enables A/B auto-tuning.

Returns: `{"status": "updated", "updated_keys": [...]}`

---

## 4. MCP Interface (agents.md section 3)

### List tools
GET /mcp/v1/tools
X-API-Key: <org-scoped API key with mcp:tools scope>

text

### Call a tool
POST /mcp/v1/tools/{tool_name}/call
X-API-Key: <org-scoped API key with mcp:tools scope>
Content-Type: application/json

{"arguments": {...}}

text

### Auth

- Header: `X-API-Key: <mcp_secret_key>`
- Scope: `mcp:tools`
- Reuses the platform's real org-scoped public API auth — same rate limiting, quota enforcement, and hashing every other /v1/* endpoint gets.

---

## 5. Where the code lives

| File | Role |
|------|------|
| `agents.md` | Contract (10 sections) |
| `api/services/mcp/builtin_tools.py` | The 4 tools |
| `api/routers/mcp_server.py` | MCP server routes |
| `tests/test_mcp_builtin_tools.py` | 9 tests, all passing |
| `api/services/evaluation_jobs.py` | Underlying eval service |
| `api/models/agent.py` | Underlying agent model |
| `api/models/evaluation.py` | Underlying failure model |

---

## 6. How to test the 4 modes
1. Get a real org API key with mcp:tools scope
2. List the 4 tools
curl -H "X-API-Key: $MCP_KEY" https://rag-saas-api-sjsm.onrender.com/mcp/v1/tools

3. Mode 1 — provision an agent
curl -X POST -H "X-API-Key: MCP_KEY" -H "Content-Type: application/json" \ -d '{"arguments": {"organization_id": "'ORG_ID'", "name": "Support Bot"}}'
https://rag-saas-api-sjsm.onrender.com/mcp/v1/tools/create_rag_agent/call

4. Mode 2 — run a benchmark
curl -X POST -H "X-API-Key: MCP_KEY" -H "Content-Type: application/json" \ -d '{"arguments": {"organization_id": "'ORG_ID'", "dataset_id": "'$DATASET_ID'"}}'
https://rag-saas-api-sjsm.onrender.com/mcp/v1/tools/run_eval_benchmark/call

5. Mode 3 — get the failure report
curl -X POST -H "X-API-Key: MCP_KEY" -H "Content-Type: application/json" \ -d '{"arguments": {"organization_id": "'ORG_ID'", "run_id": "'$RUN_ID'"}}'
https://rag-saas-api-sjsm.onrender.com/mcp/v1/tools/get_failure_report/call

6. Mode 4 — update retrieval config
curl -X POST -H "X-API-Key: MCP_KEY" -H "Content-Type: application/json" \ -d '{"arguments": {"organization_id": "'ORG_ID'", "agent_id": "'$AGENT_ID'", "config": {"top_k": 10}}}'
https://rag-saas-api-sjsm.onrender.com/mcp/v1/tools/update_retrieval_config/call

text

---

## 7. Codebase discipline (agents.md section 4)

- `pytest tests/ -x` — 314 files
- `ruff check api/`
- `cd frontend && npm run type-check`
- All Bob-Auto-Fixes logged in `ROADMAP.md` under `[Bob-Auto-Fixes]`

---

## 8. Security (agents.md section 5)

- Multi-tenant isolation (org_id + RLS PostgreSQL)
- SSRF guardrails
- No secrets in logs or commits
- No direct pushes to main
- No SQL string interpolation
- No eval() / exec() / unsafe pickle

---

## 9. Project history

Built incrementally across 25 documented development parts, each with its own audit, real test results, and honest documentation of gaps.

Full history: `docs/CAHIER_DES_CHARGES.md`
Phase 5: `ROADMAP.md`

---

## 10. License

MIT — see `LICENSE`.

---

IBM Bob 2.0 Submission — 2026
