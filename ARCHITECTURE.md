# Architecture

System-level overview of the RAG SaaS Platform. For subsystem-level detail
see [`docs/advanced/`](docs/advanced/) (RAG pipeline internals) and the
per-feature docs linked throughout.

**Subsystem deep-dives:**
- [System overview](docs/architecture/OVERVIEW.md) -- components, stack, flows
- [Data flow](docs/architecture/DATA_FLOW.md) -- RAG, agents, workflows end-to-end
- [Security model](docs/architecture/SECURITY.md) -- multi-tenancy, RLS, permissions
- [Legacy status](docs/architecture/LEGACY.md) -- src/ vs api/


## High-level components

```
                        ┌─────────────────────┐
                        │   frontend/ (Next.js) │
                        │   17 dashboard sections│
                        └──────────┬───────────┘
                                   │ REST (+ streaming)
                                   v
┌───────────────────────────────────────────────────────────────┐
│                         api/ (FastAPI)                        │
│  92 routers — auth, orgs, documents, chat, agents, workflows, │
│  evaluation, fine-tuning, media, billing, admin, security,    │
│  MCP client/server, retrieval diagnostics...                  │
└───┬───────────────┬──────────────────┬──────────────┬─────────┘
    │               │                  │              │
    v               v                  v              v
┌──────────┐  ┌───────────────┐  ┌───────────┐  ┌─────────────┐
│PostgreSQL│  │ Celery + Redis│  │S3 storage │  │External MCP │
│(Supabase)│  │background jobs│  │documents,  │  │servers (via │
│+pgvector │  │(ingestion,    │  │media,      │  │MCP client)  │
│          │  │evals, workflow│  │datasets    │  │             │
│          │  │runs, reindex) │  │            │  │             │
└──────────┘  └───────────────┘  └───────────┘  └─────────────┘
                        │
                        v
              ┌────────────────────┐
              │  litellm            │
              │  → Anthropic/OpenAI/ │
              │    Mistral/others    │
              └────────────────────┘
```

## API layer (`api/`)

- **Framework**: FastAPI, async throughout.
- **ORM**: SQLAlchemy 2.0 async, migrations via Alembic
  (`api/alembic/versions/`, head at migration `0108` as of Partie 24).
- **Auth**: session-based auth (`auth.py`, `password.py`, `two_factor.py`,
  `webauthn.py`, `oauth.py`, `enterprise_sso.py`), plus API keys for
  programmatic/agent access (`agent_api_keys.py`).
- **Multi-tenancy**: every tenant-scoped table carries an `org_id`, most
  enforce row-level security (RLS) at the database level in addition to
  application-layer checks (`security/` modules per feature, e.g.
  `api/security/fine_tuning.py`, `api/security/autonomous_agents.py`).
- **Routers**: one module per feature area under `api/routers/`, each
  paired with a `api/schemas/<feature>.py` (Pydantic request/response
  models), `api/security/<feature>.py` (access control), and usually
  `api/services/<feature>.py` (business logic) — see
  [`docs/developer/API.md`](docs/developer/API.md).

## Background jobs (Celery + Redis)

Long-running or scheduled work never runs inline in a request: document
ingestion, evaluation job execution, fine-tuning job polling, media
processing (vision, YOLO, CLIP embedding), reindexing schedules, domain
verification, backups. Task modules live under `api/tasks/`, one per
feature area, mirroring the router/service split.

## LLM access (litellm)

All LLM calls go through [litellm](https://github.com/BerriAI/litellm),
which normalizes request/response shapes across Anthropic, OpenAI,
Mistral, and other providers. This is what lets the platform support
provider choice per organization, per agent, and per fine-tuning job
without provider-specific call sites scattered through the codebase.
Real, per-request cost tracking (`api/services/cost_tracking.py`) is
built on top of litellm's reported token usage, and is reused directly
by both autonomous-agent cost tracking (Partie 23) and evaluation-job
cost reporting (Partie 7).

One deliberate exception: fine-tuning job submission talks to the
OpenAI/Mistral fine-tuning REST APIs directly via `httpx`
(`api/services/fine_tuning_providers.py`), because litellm's own
fine-tuning support doesn't cover Mistral. Anthropic has no public
fine-tuning API at all, so fine-tuning jobs targeting Anthropic are
rejected upfront with a clear `ProviderNotSupportedError` — a real,
documented gap, not a silent failure. See
[`docs/fine-tuning/OVERVIEW.md`](docs/fine-tuning/OVERVIEW.md).

## RAG pipeline

The retrieval techniques were proven out in the original single-tenant
demo (`src/`, see [`src/README.md`](src/README.md)) — hybrid BM25 +
semantic search, Reciprocal Rank Fusion, cross-encoder reranking — and
then rebuilt for multi-tenant scale in `api/services/`. See
[`docs/advanced/RAG_PIPELINE.md`](docs/advanced/RAG_PIPELINE.md),
[`docs/advanced/CHUNKING.md`](docs/advanced/CHUNKING.md),
[`docs/advanced/EMBEDDINGS.md`](docs/advanced/EMBEDDINGS.md),
[`docs/advanced/RETRIEVAL.md`](docs/advanced/RETRIEVAL.md), and
[`docs/advanced/RERANKING.md`](docs/advanced/RERANKING.md) for the
current, multi-tenant implementation.

## Workflow engine

`api/services/workflow_engine.py` is a real graph executor over a
`Workflow`'s own `nodes`/`edges` (LLM call, RAG search, web search, HTTP
call, condition, code, email, calendar, database, and a `human`
approval block that pauses the run). Each real node execution is
recorded in `WorkflowNodeExecution` (input/output/duration/status per
step, mirroring `AgentTrace`'s own per-step tracing for agents) and
streamed live over SSE (`GET /workflows/runs/{run_id}/stream`). See
[`docs/developer/API.md`](docs/developer/API.md) and
`docs/user/WORKFLOWS.md`.

## Agent function calling and MCP

`AgentOrchestrator.run_agent` runs a real, provider-native
function-calling loop (`tools=[...]` sent to the LLM, `tool_calls`
parsed and executed, results fed back as `role:"tool"` messages,
looped up to a bounded step cap). Tools come from three sources: the
platform's own built-in registry (`api/services/tools.py`), an
organization's custom webhook tools (`api/models/custom_tool.py`), and
**MCP (Model Context Protocol)** — this platform is both an MCP
*client* (agents call tools on an external MCP server an org
registers, `api/services/mcp/client.py`, using Anthropic's own `mcp`
SDK) and an MCP *server* (external MCP clients call this platform's own
tool registry over `/mcp/v1/*`, reusing the same org-scoped API-key
auth every other public endpoint uses). See
[`docs/mcp/README.md`](docs/mcp/README.md).

Cross-run agent memory (`AgentLongTermMemoryItem`, distinct from the
existing per-session short-term memory) lets a tool persist a fact
that outlives one conversation, org-wide or per-user.

## Agents vs. autonomous agents

A real, deliberate architectural split, not two names for the same
thing:

- **Agents** (`agents.py`, `custom_tools.py`) are configured chatbot
  personas — a system prompt, a tool allowlist, model config — invoked
  per conversation turn, similar to how most RAG chat products expose
  "custom assistants."
- **Autonomous agents** (`autonomous_agents.py`,
  `api/models/autonomous_agent.py`) run a real multi-step planning and
  execution loop toward a goal: `AutonomousAgent` → `AgentPlan` →
  `AgentStep`s, with persistent `AgentMemory`, bounded
  `AgentCollaboration` between agents, guardrails, and cost limits. See
  [`docs/autonomous/OVERVIEW.md`](docs/autonomous/OVERVIEW.md).

## Frontend (`frontend/`)

Next.js + React + TypeScript, tested with Vitest. One top-level
dashboard section per major feature area under `frontend/app/dashboard/`
(17 sections), each backed by its own `frontend/lib/services/*.ts` API
client and `frontend/lib/hooks/*.ts` data hooks, matching the API
router it talks to. Design is intentionally plain: light theme only, no
dark mode, an orange-and-white gradient, no decorative progress bars.

## Evaluation (Eval Lab)

A real, mature evaluation system, not just the retrieval metrics it
started from: `EvaluationDataset`/`EvaluationQuestion` (with real
ground-truth documents/answers), `EvaluationJob` (real, Celery-backed
batch runs with cancellation), `EvaluationResult` (per-question
Recall@K/MRR/NDCG/Precision/Hit-Rate, cost, latency), `ComparisonJob`
(model/retriever/reranker/prompt comparison), `RegressionDetection`
(automatic, per-organization regression alerts between two jobs), and
`DeploymentEvaluation` (a real evaluation gate before promoting an
agent version). See `docs/rag/` and `tests/test_evaluation_*.py`.

## Developer platform (API keys, webhooks, SDKs)

External developers authenticate with an org-scoped API key
(`OrganizationAPIKey`, hashed at rest, scoped, rate-limited, with
rotation/expiration), get outbound **webhooks** for real platform
events (`Webhook`/`WebhookDelivery`, HMAC-SHA256 signed, retried with
backoff), and can use one of three real, tested SDKs shipped in this
repo: [`sdks/python/`](sdks/python/), [`sdks/js/`](sdks/js/), and
[`sdks/react/`](sdks/react/) (a widget-embedding React component). See
[`docs/developer/API.md`](docs/developer/API.md).

## Observability

Beyond the OpenTelemetry/Loki/Grafana stack (`docker-compose.observability.yml`,
off unless configured), the platform tracks retrieval quality and
performance directly: `RetrievalDiagnostic` records the resolved
strategy, final ranked chunks, and latency for every LIVE chat query
(not just Eval Lab questions), `AgentTrace`/`WorkflowNodeExecution`
give per-step execution history for agents and workflows, and
`OrganizationUsage` tracks tokens/cost per organization. Sentry
(`api/security/error_tracking.py`) captures backend + Celery errors
when `SENTRY_DSN` is configured. See
[`docs/install/OBSERVABILITY_STACK.md`](docs/install/OBSERVABILITY_STACK.md).

## Diagrams

Renderable Mermaid diagrams for this architecture, the database schema,
the RAG pipeline, the auth flow, deployment topology, and multi-tenancy
are in [`docs/diagrams/`](docs/diagrams/).
