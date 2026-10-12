# 00 - Executive overview of RAG SaaS Platform

Written 2026-10-12 for a reader (human or AI) who has never seen the project. Everything below was checked in the repository on branch `bob/auto-fix-20261010-gaps` unless marked otherwise.

## How to read the evidence tags
| Tag | Meaning |
|---|---|
| **[V]** | read in the code (or in the generated inventories in `annex/`) while writing this dossier |
| **[R]** | a test, measurement or command that was actually run during the project's working sessions (the run output existed; it is not re-run here) |
| **[D]** | stated in a repository document (README, ROADMAP, DECISIONS, audit CSV) and not re-verified now |
| **[U]** | unknown / not retrievable |

A statement without a tag is a plain explanation of a mechanism that follows from the cited code.

## 1. What the product is
**Name:** "RAG SaaS Platform" (owner's decision D3, `docs/DECISIONS.md`; no logo yet). **Owner:** Naomy Tcheums, a freelance developer based in Cameroon. **Licence:** MIT [D].

A multi-tenant web platform where an **organization** signs up, uploads or connects its documents, configures one or more AI **assistants (agents)**, and gets answers **grounded in its own documents with citations to the exact source passages**. Around that core it sells: strict isolation between customers, spend control (prepaid credits, plans, quotas), an **Evaluation Lab** that measures retrieval and answer quality, and a set of automation features (autonomous agents, workflows, MCP/A2A interoperability, connectors, voice, fine-tuning, white-label).

It can be self-hosted (Docker Compose) or run as a SaaS [D: README].

### Problem solved
Companies want an assistant that answers from their private documents, can be trusted (citations, refusal when the context is missing), can be measured (is it getting better or worse?) and is safe to run for several customers on one platform. Most demos stop at "it answers"; this one adds measurement (Recall/MRR/NDCG), tenancy, billing and operations.

### Differentiating features (all present in code, maturity varies - see 11_KNOWN_ISSUES)
1. **Eval Lab with a closed quality loop**: datasets of questions with expected documents, jobs that run a candidate configuration, Recall@1/3/5/10, MRR, NDCG, precision, hallucination rate, latency, tokens, cost; comparison between runs; failure categories (retrieval vs generation). [V: `api/services/evaluation_results.py`, `retrieval_metrics.py`, routes in `annex/api_routes.csv`]
2. **Policy- and tenant-aware retrieval**: every chunk query is scoped by `organization_id`; an optional OPA/Rego policy filter can be applied at search time (`policy_aware_retrieval_enabled`, default off). [V]
3. **Bidirectional MCP and A2A**: the platform is an MCP *client* (calls external tool servers, behind a firewall) and an MCP *server* (exposes four built-in tools to an external agent), plus an A2A endpoint. [V]
4. **Per-organization credentials for 40 connectors** (Jira, Zendesk, Drive, Notion, Confluence, GitHub, Salesforce...), encrypted, default-deny. [V: `api/services/connector_credentials.py`, migration 0143]
5. **Two-stage prompt-injection detector** (classifier + language-model second opinion). [V/R]
6. **Bring-your-own-key and prepaid credits** for LLM spend. [V]

### What is NOT yet a finished commercial product
No payment provider is usable for the owner's situation (Stripe needs a company in a supported country; Paystack does not serve Cameroon; CinetPay is not implemented - D14/D16). A persistent Celery worker is not part of the documented free-tier deployment (a scheduled GitHub Actions job drains the queue every 10 minutes). Row-level security is enabled without policies. See `11_KNOWN_ISSUES_AND_REMAINING_WORK.md`.

## 2. Customers and users
| Role | Who | Main surfaces |
|---|---|---|
| Visitor | prospect | landing page `/`, `/login`, `/register`, public widget demo |
| End user / member | employee of a customer organization | `/chat`, conversation history, feedback |
| Manager / admin / owner of an organization | customer administrator | `/dashboard/*` (documents, agents, eval, billing, connectors, API keys, webhooks, teams, white-label, security) |
| Developer | integrator | public `/v1` API, API keys, SDKs, embeddable widget, MCP server |
| Superadmin | the platform operator (the owner) | `/admin` (users, organizations, subscriptions, system health) |
| Partner / reseller | sales channel | `/dashboard/partners`, commissions |

## 3. Typical customer journey (what the code supports)
1. **Register** (`POST /auth/register`, form `frontend/app/register/page.tsx`), verify e-mail (Resend), optionally enable 2FA (TOTP, WebAuthn).
2. **Create/join an organization** (an organization row is created at sign-up; invitations for others), choose settings (language, embedding model, retrieval strategy).
3. **Upload documents** (PDF, DOCX, TXT, Markdown, HTML, CSV, JSON, XML, EPUB, images with OCR, audio/video) or **import** from a URL, a sitemap, GitHub, Drive, Docs, Notion, Confluence, OneDrive. Antivirus scan (ClamAV, off by default), extraction, chunking, embedding, indexing run in the background (Celery).
4. **Create an agent** (prompt, model, tools, knowledge base, guardrails, memory) or use the Factory to generate one from a plain-language requirement.
5. **Chat** at `/chat`: the question is retrieved against the organization's chunks, the agent answers with streaming and `[n]` citations; users give feedback.
6. **Measure**: build an evaluation dataset, run a job, read Recall/MRR/NDCG, compare configurations, set quality alerts (Guardian).
7. **Operate and pay**: plans, credits, invoices, usage alerts, webhooks, API keys; embed the widget or call the public API.

## 4. Size of the system (generated inventories, 2026-10-12) [V]
| Item | Count | Source |
|---|---:|---|
| HTTP operations in OpenAPI | 983 across 99 tags | `annex/api_routes.csv` |
| Database tables | 182 (83 carry `organization_id`) | `annex/database_tables.csv` |
| Alembic migrations | 143 (head `0143`) | `annex/migrations.csv` |
| Frontend pages (`page.tsx`) | 64 | `annex/frontend_pages.csv` |
| Backend Python modules | routers 107, services 290, tasks 50, security 72, models 90, tools 10 | `annex/python_modules.md` |
| Test files / test functions | 512 / 5,604 (6,386 test cases after parametrisation in the last full CI run) | `annex/tests_inventory.csv`, CI [R] |
| Catalogued features (cahier des charges) | 514 | `12_COMPLETE_FEATURE_CATALOG.md` |

## 5. Architecture in one paragraph
A **FastAPI** application (`api/main.py`) exposes the REST API; **Next.js 16 / React 19** (`frontend/`) is the web client; **PostgreSQL + pgvector** (hosted on Supabase in production [D]) stores everything including vectors (HNSW index); **Redis** serves cache, rate limiting and the **Celery** broker; **S3-compatible storage** (MinIO locally) stores uploaded files; **LiteLLM** routes calls to Anthropic, OpenAI, Mistral, Gemini, Ollama, watsonx or any OpenAI-compatible server; local **sentence-transformers** models produce embeddings by default. Details: `03_TECHNICAL_ARCHITECTURE.md`.

## 6. State of the work on 2026-10-12
* **Code:** feature-rich; 514 catalogued features; 422 are closed (283 verified complete + 114 fixed and tested + 25 owner decisions) and 92 are not yet proven (13 validated by tools but never deployed, 34 implemented but unverified, 19 written but never executed, 26 blocked by external accounts) [R: audit CSV].
* **Tests:** the full backend suite (6,386 cases) passes on GitHub CI (`backend-tests`) [R]; 15 audit Parts have a recorded green run [R].
* **Production database:** migrated to revision `0143` on 2026-10-11 after a verified backup (27 MB, 217 tables with data) and a successful rehearsal [R]. The application code of the PR #25 is **not yet merged or deployed** at the time of writing; the old code works with the new schema because the 7 migrations (0137-0143) are additive.
* **Open pull request:** #25 (`bob/auto-fix-20261010-gaps` -> `main`). CI: all GitHub checks green except non-blocking `mypy` and `bandit`; the CircleCI `api-tests` job was being repaired (see 10_TESTS_CI_CD_AND_DEPLOYMENT.md) and its latest result had not been observed when this was written.
* **Commercial readiness:** not ready to charge customers (no usable payment provider, no persistent worker/monitoring decided, secrets to rotate). Ready for a closed trial after the steps in `11_KNOWN_ISSUES_AND_REMAINING_WORK.md` section "Release steps".

## 7. Where to go next in this dossier
| You want to know... | Read |
|---|---|
| How it came to be | `01_PROJECT_HISTORY.md` |
| What every module does for a user | `02_PRODUCT_FUNCTIONAL_SPEC.md` |
| How the code is organised | `03_TECHNICAL_ARCHITECTURE.md` |
| Exactly how a question becomes an answer | `04_RAG_PIPELINE_DEEP_DIVE.md` |
| Agents, FACTORY/GUARDIAN/AUTOPSY/CHANGELAB, MCP, workflows | `05_AGENTS_AND_AUTOMATIONS.md` |
| Security and tenant isolation | `06_SECURITY_AND_TENANCY.md` |
| Tables and migrations | `07_DATABASE_AND_MIGRATIONS.md` |
| Routes, pages, SDKs | `08_API_FRONTEND_AND_SDKS.md` |
| Money and external services | `09_BILLING_CONNECTORS_AND_EXTERNAL_SERVICES.md` |
| Tests, CI, deployment | `10_TESTS_CI_CD_AND_DEPLOYMENT.md` |
| What is broken or missing and why | `11_KNOWN_ISSUES_AND_REMAINING_WORK.md` |
| Every feature one by one | `12_COMPLETE_FEATURE_CATALOG.md` |
| Vocabulary and commands | `13_GLOSSARY_AND_DEVELOPER_GUIDE.md` |
| A single file to hand to another AI | `14_AI_HANDOVER_CONTEXT.md` |
