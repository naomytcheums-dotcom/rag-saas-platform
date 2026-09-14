# Architecture

System-level overview of the RAG SaaS Platform. For subsystem-level detail
see [`docs/advanced/`](docs/advanced/) (RAG pipeline internals) and the
per-feature docs linked throughout.

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
│  89 routers — auth, orgs, documents, chat, agents, workflows, │
│  evaluation, fine-tuning, media, billing, admin, security...  │
└───────┬───────────────────────┬──────────────────┬────────────┘
        │                       │                   │
        v                       v                   v
┌───────────────┐    ┌────────────────────┐   ┌─────────────┐
│  PostgreSQL    │    │  Celery + Redis     │   │  S3 storage │
│  (Supabase)    │    │  background jobs     │   │  documents, │
│  + pgvector    │    │  (ingestion, evals,  │   │  media,     │
│                │    │  fine-tuning polling, │   │  datasets   │
│                │    │  reindexing, ...)     │   │             │
└───────────────┘    └────────────────────┘   └─────────────┘
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

## Diagrams

Renderable Mermaid diagrams for this architecture, the database schema,
the RAG pipeline, the auth flow, deployment topology, and multi-tenancy
are in [`docs/diagrams/`](docs/diagrams/).
