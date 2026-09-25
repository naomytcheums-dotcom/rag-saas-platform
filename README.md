# IBM BOB 2.0 — RAG EVOLUTION FACTORY

**An IBM Bob-powered autonomous engineering system that creates, evaluates, diagnoses and improves RAG agents through a closed-loop workflow.**

> **IBM Bob** is the autonomous engineering brain.
> **RAG Evolution Factory** is the orchestration system.
> **The RAG platform** is the real environment Bob operates, measures and evolves.
> **MCP** is the control interface between Bob and the platform.

🌐 **Live demo**: https://rag-saas-platform-rho.vercel.app
🔧 **Live API**: https://rag-saas-api-sjsm.onrender.com
📖 **Submission doc**: [docs/ibm_bob_2/SUBMISSION.md](docs/ibm_bob_2/SUBMISSION.md)

---

## The closed loop
+----------------------+
| IBM BOB 2.0 |
| Autonomous Engineer |
+----------+-----------+
|
v
+-------------------------+
| RAG EVOLUTION FACTORY |
+------------+------------+
|
+-----------------+-----------------+
v v v
+---------+ +----------+ +---------+
| FACTORY |------>| GUARDIAN |----->| AUTOPSY |
+---------+ +----------+ +----+----+
|
v
+------------+
| CHANGELAB |
+-----+------+
|
tests + benchmark
|
v
+------------------+
| KEEP / ROLLBACK |
+--------+---------+
|
v
GUARDIAN

text

---

## The 4 modes (agents.md contract)

| Mode | MCP Tool | What Bob does |
|------|----------|---------------|
| **1 - FACTORY** | `create_rag_agent` | Bob provisions a real multi-tenant RAG agent |
| **2 - GUARDIAN** | `run_eval_benchmark` | Bob monitors real metrics (Recall@K, MRR, NDCG, hallucination) |
| **3 - AUTOPSY** | `get_failure_report` | Bob investigates and categorizes failures |
| **4 - CHANGELAB** | `update_retrieval_config` | Bob experiments, re-benchmarks, keeps or rolls back |

**Exposed via MCP**:
- `GET /mcp/v1/tools` — lists the 4 tools
- `POST /mcp/v1/tools/{name}/call` — executes a tool

**Source**: [api/services/mcp/builtin_tools.py](api/services/mcp/builtin_tools.py)
**Tests**: [tests/test_mcp_builtin_tools.py](tests/test_mcp_builtin_tools.py) — 9 cases, all passing.

---

## What Bob actually does end-to-end
PROBLEM
RAG systems degrade over time. Developers currently have to manually
detect, diagnose and fix those regressions.
|
v
BOB DETECTS
GUARDIAN -> run_eval_benchmark -> Recall@5 = 0.72 (WARNING)
|
v
BOB DIAGNOSES
AUTOPSY -> get_failure_report -> RETRIEVAL_FAILURE dominant (18/28)
|
v
BOB EXPERIMENTS
CHANGELAB -> update_retrieval_config (top_k 5 -> 10)
|
v
BOB VALIDATES
GUARDIAN -> run_eval_benchmark -> Recall@5 = 0.84 (MERGED)
|
v
RESULT
+0.12 Recall@5 improvement, automatic rollback if regression

text

**Full example**: [ROADMAP.md](ROADMAP.md) under `[Bob-Auto-Fixes]`.

---

## Underlying RAG SaaS platform

The RAG SaaS platform below provides the **real, production-oriented environment** on which Bob operates. It is not the hero of this repository — it is the **complex, real system** that makes Bob's autonomous engineering loop meaningful.

---

## Key numbers

| Metric | Value |
|--------|-------|
| API routers | 89 |
| Frontend sections | 17 |
| Backend test files | 314 |
| i18n languages | 6 (EN, FR, ES, DE, PT, AR) |
| Translations | ~4,200 keys |
| RBAC permissions | 52 |
| CRM connectors | 36 |
| Alembic migrations | 118 |
| IBM Bob 2.0 modes | 4 (all implemented) |

---

## What the RAG platform does

### Multi-tenant
- Organizations, teams, workspaces, members
- Granular RBAC (52 permissions), resource-level permissions
- SSO (SAML/OAuth), 2FA (TOTP), WebAuthn (physical keys), invitations

### Documents
- Upload, ingestion, chunking, embeddings
- Hybrid search (BM25 + semantic + cross-encoder reranking)
- Citations with source, page, chunk, relevance
- External connectors (Slack, Teams, Discord, n8n, Airbyte, Notion, Confluence, Google Drive, OneDrive, GitHub, +34 CRM)

### Chat & conversation
- Streaming chat (SSE) with citations, feedback, sharing
- Voice messages + text-to-speech
- Embeddable widget (unified theme, allowed domains)

### Agents
- Configured agents: prompt + tools + guardrails + BYOK
- Autonomous agents: multi-step planning, tool-calling loop, long-term memory, bounded agent-to-agent collaboration, guardrails, per-step/per-agent USD cost tracking

### Workflows
- Multi-step orchestration on Celery
- Blocks: LLM, RAG, web search, HTTP, code, condition, human, email, calendar, database
- Triggers: webhook, schedule, manual

### Evaluation & quality
- Evaluation datasets, jobs, results, comparisons
- Benchmark versions + rollback
- Regression detection with configurable thresholds
- Quality dashboard

### Fine-tuning
- Dataset upload (JSONL), validation
- Jobs for OpenAI + Mistral (Anthropic has no public fine-tuning API — gap documented, not faked)
- Deployment of fine-tuned models

### Media & vision
- Media processing, vision-in-documents
- Object detection (YOLOv8, local inference)
- CLIP visual search (image-to-image, text-to-image)

### Analytics & observability
- Usage analytics, audit logs, agent traces
- Observability endpoints (Prometheus + Sentry + Loki)
- Human-approval workflows

### Billing & sales
- Subscriptions, quotas, usage-based billing
- Stripe + Paystack
- Partner/sales program

### White-label & branding
- Custom domains, SSL certificates
- Org branding (logo, colors, font, custom CSS)
- Branded emails (7 org-level templates)
- Widget with unified branding

### Marketplace & plugins
- Plugin system + marketplace
- Custom tools (webhooks)

### Security & compliance
- Encryption, compliance tooling, security scanning
- Audit trails, PostgreSQL RLS
- backend-security CI (12 CVEs fixed)

### Admin dashboard
- Organization/user/subscription management for platform operators

### MCP (Model Context Protocol)
- MCP Server: exposes internal tools + the 4 IBM Bob modes
- MCP Client: consumes external MCP servers

---

## Tech stack

| Layer | Choice |
|-------|--------|
| API | FastAPI, SQLAlchemy 2.0 (async), PostgreSQL (Supabase), Alembic |
| Background jobs | Celery + Redis |
| LLM access | litellm (Anthropic, OpenAI, Mistral, + BYOK) |
| Frontend | Next.js 16, React, TypeScript, TailwindCSS |
| Frontend tests | Vitest |
| Backend tests | pytest (314 files) |
| Object storage | S3-compatible (AWS, Cloudflare R2) |
| Vision / media | YOLOv8 (ultralytics, local), CLIP (openai/clip-vit-base-patch32) + faiss-cpu |
| Monitoring | Prometheus, Grafana, Sentry, Loki |
| i18n | 6 languages (EN, FR, ES, DE, PT, AR), English by default |

---

## Getting started

### Self-hosted (Docker)

```bash
git clone https://github.com/naomytcheums-dotcom/rag-saas-platform.git
cd rag-saas-platform
cp .env.example .env
./install.sh
docker compose -f docker-compose.selfhosted.yml up -d
SaaS (Vercel + Render)
Frontend: https://rag-saas-platform-rho.vercel.app

Backend: https://rag-saas-api-sjsm.onrender.com

Documentation
Full documentation lives under docs/ — start at docs/index.md:

docs/user/ — end-user guides

docs/admin/ — org + platform administration

docs/developer/ — architecture, API, SDKs, webhooks

docs/install/ — deployment, environment, upgrades, backups

docs/api/ — REST API, OpenAPI, Swagger, Redoc

docs/advanced/ — RAG pipeline internals

docs/diagrams/ — architecture, database, RAG, auth, deployment

docs/ibm_bob_2/SUBMISSION.md — IBM Bob 2.0 submission document

agents.md — IBM Bob 2.0 contract (10 sections)

See also:

ARCHITECTURE.md — system-level overview

ROADMAP.md — what's planned + [Bob-Auto-Fixes]

GLOSSARY.md — platform-specific terminology

Tests
bash
pytest tests/ -x
pytest tests/eval/ -x
ruff check api/
cd frontend && npm run type-check
314 backend test files, all green.

Internationalization
6 languages: English (default), French, Spanish, German, Portuguese, Arabic

~4,200 translations in locales/

i18n system: custom (frontend/lib/i18n.tsx), backend (api/services/i18n.py)

License
MIT — see LICENSE.

Project history
Built incrementally across 25 documented development parts, each with its own audit, real (never fabricated) test results, and honest documentation of gaps and limitations.

The full history is in docs/CAHIER_DES_CHARGES.md.

IBM Bob 2.0 integration (Phase 5): see ROADMAP.md.

Contributing
See CONTRIBUTING.md and CODE_OF_CONDUCT.md. Security issues should be reported per SECURITY.md.

IBM Bob 2.0 Submission — 2026
