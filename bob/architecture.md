# Architecture — How IBM Bob interacts with the platform

## High-level
+----------------------+
| IBM BOB 2.0 |
| Autonomous Engineer |
+----------+-----------+
|
| MCP (HTTP + X-API-Key)
v
+-------------------------+
| RAG EVOLUTION FACTORY |
| (MCP server, this repo)|
+------------+------------+
|
+---------+---------+---------+---------+
v v v v v
FACTORY GUARDIAN AUTOPSY CHANGELAB Eval Lab
| | | | |
+---------+---------+---------+---------+
|
v
+-----------------------+
| RAG SaaS Platform |
| FastAPI / PostgreSQL |
| pgvector / Celery |
+-----------------------+

text

## Component roles

| Component | Role |
|-----------|------|
| IBM Bob 2.0 | Autonomous engineering brain. Decides what to build, measure, diagnose, fix. |
| MCP server | Exposes the 4 tools to Bob over HTTP. Lives in `api/routers/mcp_server.py`. |
| FACTORY | Provisions RAG agents. Backed by `api/models/agent.py`. |
| GUARDIAN | Runs benchmarks. Backed by `api/services/evaluation_jobs.py`. |
| AUTOPSY | Categorizes failures. Backed by `api/models/evaluation.py`. |
| CHANGELAB | Experiments + re-benchmarks. Backed by `Agent.knowledge_base_config`. |
| Eval Lab | Real evaluation datasets, jobs, results, comparisons. |
| RAG SaaS Platform | Real production-grade environment Bob operates. |

## Auth

- Header: `X-API-Key: <org-scoped key>`
- Scope: `mcp:tools`
- Isolation: every tool call is scoped to one organization (`organization_id`)
- Reuse: same auth as every other `/v1/*` public endpoint

## Data flow
Bob sends MCP request
|
v
POST /mcp/v1/tools/{name}/call
|
v
api/routers/mcp_server.py
|
v
api/services/mcp/builtin_tools.py
|
v
Real service (Agent / EvaluationJob / ...)
|
v
PostgreSQL / pgvector
|
v
MCP response back to Bob

text

## Safety

- Multi-tenant: `organization_id` required on every tool
- No cross-org leak: queries filtered by `organization_id`
- No secrets in logs
- No direct `main` push: Bob works on `bob/auto-fix-*` branches
- Rollback guaranteed: if new benchmark < baseline, revert

## Where the code lives

| File | Role |
|------|------|
| `api/services/mcp/builtin_tools.py` | The 4 tools (Bob) |
| `api/routers/mcp_server.py` | MCP server routes |
| `tests/test_mcp_builtin_tools.py` | 9 tests |
| `api/models/agent.py` | Agent model |
| `api/services/evaluation_jobs.py` | Eval service |
| `api/models/evaluation.py` | Failure model |
