# 13 - Glossary and developer guide

## 1. Glossary (business and technical terms, alphabetical)
| Term | Meaning in this project |
|---|---|
| **A2A (Agent2Agent)** | open protocol (Google, Linux Foundation) for one AI agent to call another; this platform exposes one agent capability over it (`api/routers/a2a.py`). No A2A client. |
| **Agent** | a configured assistant (`agents` row): prompt, model, tools, knowledge base, guardrails, memory. Run by `AgentOrchestrator`. |
| **Alembic** | database migration tool; migrations in `api/alembic/versions` (never edit an existing one). |
| **API key (organization)** | secret a customer's program uses against `/v1` and MCP, with scopes, expiry, quota. |
| **Autopsy** | Bob mode 3: classify why an evaluation failed (retrieval vs generation). |
| **Bearer token / JWT** | short-lived access token sent in `Authorization`; refreshed with an httpOnly cookie. |
| **BM25** | classic keyword-ranking formula; the lexical half of hybrid search (`rank_bm25`). |
| **Bob (IBM Bob 2.0)** | IDE/CLI AI coding assistant used as "Lead AI Systems Engineer" in a contest entry; interacts with the platform through MCP tools. Not a production runtime. |
| **BYOK** | bring your own (LLM provider) key: the organization pays its provider directly and is not debited credits. |
| **Celery / beat** | background job system (worker) and its periodic scheduler (beat), brokered by Redis. |
| **ChangeLab** | Bob mode 4: change configuration, test, benchmark, keep or roll back. |
| **Chunk** | a passage of a document (default 512 tokens, 50 overlap) stored with its embedding. |
| **Citation** | link from `[n]` in an answer to the exact chunk/document/page it came from. |
| **Context compression** | shrinking retrieved text before it goes into the prompt (optional). |
| **Credit** | prepaid unit of platform usage (1 credit = 1 request = 100 input tokens = 50 output tokens = 1 document). |
| **Cross-encoder (reranker)** | model that reads (query, chunk) pairs together to re-order candidates; `ms-marco-MiniLM-L-6-v2`. |
| **Dataset (evaluation)** | set of questions with expected documents used to score retrieval/answers. |
| **Embedding** | vector of numbers representing meaning; MiniLM-L6-v2 gives 384 numbers. |
| **Evolution engine** | proposes a better prompt (via DSPy), re-runs the benchmark, recommends only on a measured gain; never auto-applies. |
| **Factory** | Bob mode 1: provision a RAG agent; also a rules-based blueprint generator (`agent_factory.py`). |
| **Flight recorder** | per-stage timing and data of a retrieval/answer (`flight_recordings`). |
| **Guardian** | Bob mode 2: watch metrics, alert on degradation (`alerting.py`, quality alerts). |
| **Guardrails** | per-agent safety checks (blocked topics, content filter, injection detection, domain allow-list, length). |
| **HNSW** | approximate nearest-neighbour index used by pgvector (migration 0128). |
| **Hybrid search** | vector search + BM25 fused with RRF (the default strategy). |
| **HyDE** | Hypothetical Document Embeddings: embed an LLM-written hypothetical answer instead of the question. |
| **Hold-out / tuning split** | questions reserved for final scoring vs questions used to tune settings (`evaluation_questions.split`). |
| **LiteLLM** | library that routes calls to many LLM providers; used with direct adapters. |
| **MCP** | Model Context Protocol: standard for an AI client to discover and call tools on a server. The platform is client and server. |
| **MMR** | Maximal Marginal Relevance: re-selects results to balance relevance and diversity. |
| **MRR / NDCG / Recall@k / Precision@k** | retrieval metrics: mean reciprocal rank of the first relevant result; ranking-quality score with graded relevance; share of expected documents found in the top k; share of top-k that is relevant. |
| **Multi-tenant** | many customers (organizations) share the same running system and database with logical separation. |
| **OPA / Rego** | Open Policy Agent policy engine and its language; optional access filter on retrieval and MCP calls. |
| **Organization (tenant)** | the customer account; owns workspaces, documents, agents, credits. |
| **pgvector** | PostgreSQL extension for vector columns and similarity search. |
| **RAG** | Retrieval-Augmented Generation: retrieve relevant passages, then have an LLM answer from them. |
| **RBAC** | role-based access control (owner/admin/manager/member/viewer + custom roles). |
| **RLS** | PostgreSQL Row Level Security; enabled on all tables but with **no policies**, so it is not currently an isolation barrier. |
| **RRF** | Reciprocal Rank Fusion: merges ranked lists by summing 1/(k+rank); k = 60. |
| **SCIM** | standard to provision users from an identity provider. |
| **SSE** | Server-Sent Events: one-way streaming used for chat tokens. |
| **SSRF** | server-side request forgery: making the server call internal addresses; blocked by `ssrf_safe_client`. |
| **SSO / OIDC / SAML** | single sign-on; OIDC is built, SAML is not (D1/D9). |
| **Workspace** | subdivision of an organization's content. |
| **Workflow** | graph of blocks (LLM, RAG, HTTP, code, human...) executed by `workflow_engine`. |
| **Part / Étape / Phase / Hardening Mission §** | numbering of the cahier des charges and of work sessions (see 01_PROJECT_HISTORY section 4). |
| **D1..D17** | decisions recorded in `docs/DECISIONS.md`. |
| **BILL-/TEN-/RAG-/SADM-/SEC-/R- ids** | finding identifiers from audits (billing, tenancy, RAG, super-admin, security, recommendations). |

## 2. Where to find things quickly
| I need... | Look at |
|---|---|
| a route | `annex/api_routes.csv`, then the router file named by the tag (`api/routers/<tag>.py`) |
| a table | `annex/database_tables.md` |
| why something was decided | `docs/DECISIONS.md` (D1-D17) |
| a status of a feature | `12_COMPLETE_FEATURE_CATALOG.md` or `audit-reports/functional-audit-2026-10-10/10-final-status-2026-10-11.md` |
| a past fix log | `ROADMAP.md` sections "[Bob-Auto-Fixes]" |
| how to release | `docs/RELEASE_RUNBOOK_2026-10-11.md` |
| a setting | `api/config.py` (global) and `api/security/organization_settings.py::DEFAULT_SETTINGS` (per organization) |
| the legacy prototype | `src/`, `dashboard/`, root `Dockerfile`, root `render.yaml` |

## 3. Conventions to follow when changing code
* New route: place it in the matching `api/routers/*.py`, add a `require_*` dependency, scope every query by `organization_id`, add tests for allowed role, forbidden role and another tenant's id; `tests/test_route_auth_classification.py` must stay green.
* New table/column: write a **new** Alembic migration (additive, reversible, enable RLS like every table since 0131); test upgrade/downgrade on a disposable PostgreSQL; do not edit old migrations.
* New outbound HTTP call: use `ssrf_safe_client()` for any customer-influenced URL; vendor-fixed hosts are inventoried in `tests/test_outbound_http_inventory.py`.
* New stored secret: encrypt with `api/security/encryption.py::encrypt_data`; never log or return it.
* New setting: add to `api/config.py` with a safe default; per-organization behaviour goes in `DEFAULT_SETTINGS` with default **off** for anything that changes retrieval.
* Language strings: edit `locales/<code>/common.json`, then `python scripts/sync_frontend_locales.py`.
* Type ratchet: do not lower `FLOOR_PERCENT` in `tests/test_type_hint_coverage.py`; annotate new functions.
* Formatting: `ruff format` (D6); lint `ruff check api/`.
* Never: edit existing migrations, push to `main`, run tests against the real `.env`, use `eval/exec`, build SQL with f-strings, expose endpoints without auth (`agents.md` section 5).

## 4. Common commands
```bash
# tests (local disposable stack; blanks hosted and paid services)
bash scripts/run_tests_local.sh tests/test_connector_credentials.py -q
RUN_REAL_LLM_TESTS=1 LOCAL_LLM_BASE_URL=http://127.0.0.1:11434 LOCAL_LLM_MODEL=qwen2.5:3b bash scripts/run_tests_local.sh tests/llm_optin/test_local_llm_providers.py -q
# migrations
alembic upgrade head          # local; production: python scripts/migrate.py (rehearsal) then --apply
# injection measurement (needs the classifier cached and Ollama running)
RAG_ENV_FILE=.no-env PROMPT_INJECTION_CONFIRM_PROVIDER=ollama PROMPT_INJECTION_CONFIRM_MODEL=qwen2.5:7b OLLAMA_BASE_URL=http://127.0.0.1:11434 python scripts/measure_injection_two_stage.py
# regenerate this dossier's inventories
python docs/project-handover/annex/generate_inventories.py
python docs/project-handover/annex/generate_feature_catalog.py
# frontend
cd frontend && npm run lint && npm run type-check && npm test
# production smoke
python scripts/post_deploy_smoke.py --api https://<api> --frontend https://<site>
```
Windows notes: use the repository venv's Python explicitly; beat runs as a separate process (no `-B`); `backup.sh` needs LF line endings.

## 5. Diagnosing common problems
| Symptom | First checks |
|---|---|
| Uploaded document stays `pending` | is a Celery worker running and connected to the same Redis? `requeue-stale-pending-documents` needs beat; check `documents.indexing_error` |
| Answers have no citations / "no context" | does the organization have `completed` documents? embedding dimension mismatch (`dimension_mismatch_excluded`)? retrieval threshold dropping candidates? use `GET /responses/{id}/trace` |
| 403 "has not connected" on an import | the organization has not stored credentials on `/dashboard/settings/connectors` (by design) |
| 503 on saving connector credentials | `ENCRYPTION_MASTER_KEY` not set |
| Login 500 after deploy | code deployed before migrations (`users.job_title` missing): apply migrations first |
| `EMAXCONNSESSION` | too many connections on the Supabase session pooler: use the transaction pooler, keep the small pool |
| Tests failing with connection refused on `localhost:9000` | MinIO not running or killed; in CI this was memory pressure |
| Injection second opinion always "unavailable" | provider not configured, or the model is not loaded and the timeout (15 s default) is too short for a CPU model |
| `ModuleNotFoundError: pgvector` | wrong Python interpreter (use the project venv) |
