# RAG SaaS Platform

**A multi-tenant, production-oriented RAG SaaS platform, built across 25 documented development parts.**

🌐 **Live demo**: [https://rag-saas-platform-rho.vercel.app](https://rag-saas-platform-rho.vercel.app)
🔧 **Live API**: [https://rag-saas-api-sjsm.onrender.com](https://rag-saas-api-sjsm.onrender.com)
📖 **API Docs (Swagger)**: [https://rag-saas-api-sjsm.onrender.com/docs](https://rag-saas-api-sjsm.onrender.com/docs)
📊 **Metrics (Prometheus)**: [https://rag-saas-api-sjsm.onrender.com/metrics](https://rag-saas-api-sjsm.onrender.com/metrics)

---

## 🎯 IBM Bob 2.0 Submission

**The 4 modes from the [`agents.md`](agents.md) contract are actually implemented and exposed via MCP**:

| Mode | MCP Tool | Description |
|------|----------|-------------|
| **Mode 1 — FACTORY** | `create_rag_agent` | Provision a multi-tenant RAG agent |
| **Mode 2 — GUARDIAN** | `run_eval_benchmark` | Monitor metrics (Recall@K, MRR, NDCG, hallucination) |
| **Mode 3 — AUTOPSY** | `get_failure_report` | Investigate and categorize failures (RETRIEVAL_FAILURE, GENERATION_HALLUCINATION, …) |
| **Mode 4 — CHANGELAB** | `update_retrieval_config` | A/B auto-tuning + automatic rollback |

**Exposed by**:
- `GET /mcp/v1/tools` — lists the 4 tools
- `POST /mcp/v1/tools/{name}/call` — executes a tool

**Source**: [`api/services/mcp/builtin_tools.py`](api/services/mcp/builtin_tools.py)
**Tests**: [`tests/test_mcp_builtin_tools.py`](tests/test_mcp_builtin_tools.py) — 9 cases, all passing.

---

## 📊 Key numbers

| Metric | Value |
|--------|-------|
| **API routers** | 89 |
| **Frontend sections** | 17 |
| **Backend test files** | 314 |
| **i18n languages** | 6 (EN, FR, ES, DE, PT, AR) |
| **Translations** | ~4,200 keys |
| **RBAC permissions** | 52 |
| **Alembic migrations** | 118 |
| **Documented parts** | 25 |
| **IBM Bob 2.0 modes** | 4 (all implemented) |

---

## 🚀 What the platform does

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
- **Configured agents**: prompt + tools + guardrails + BYOK
- **Autonomous agents**: multi-step planning, tool-calling loop, long-term memory, bounded agent-to-agent collaboration, guardrails, per-step/per-agent USD cost tracking

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
- CLIP visual search (image→image, text→image)

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
- **MCP Server**: exposes internal tools + the 4 IBM Bob modes
- **MCP Client**: consumes external MCP servers

---

## 🛠 Tech stack

| Layer | Choice |
|-------|--------|
| **API** | FastAPI, SQLAlchemy 2.0 (async), PostgreSQL (Supabase), Alembic |
| **Background jobs** | Celery + Redis |
| **LLM access** | litellm (Anthropic, OpenAI, Mistral, + BYOK) |
| **Frontend** | Next.js 16, React, TypeScript, TailwindCSS |
| **Frontend tests** | Vitest |
| **Backend tests** | pytest (314 files) |
| **Object storage** | S3-compatible (AWS, Cloudflare R2) |
| **Vision / media** | YOLOv8 (ultralytics, local), CLIP (openai/clip-vit-base-patch32) + faiss-cpu |
| **Monitoring** | Prometheus, Grafana, Sentry, Loki |
| **i18n** | 6 languages (EN, FR, ES, DE, PT, AR), English by default |

---

## 🚀 Getting started

### Self-hosted (Docker)

```bash
git clone https://github.com/naomytcheums-dotcom/rag-saas-platform.git
cd rag-saas-platform
cp .env.example .env
# fill in the required secrets in .env (see docs/install/ENVIRONMENT.md)
./install.sh
docker compose -f docker-compose.selfhosted.yml up -d
SaaS (Vercel + Render)
Frontend: deployed on Vercel → https://rag-saas-platform-rho.vercel.app

Backend: deployed on Render → https://rag-saas-api-sjsm.onrender.com

📖 Documentation
Full documentation lives under docs/ — start at docs/index.md:

docs/user/ — end-user guides

docs/admin/ — org + platform administration

docs/developer/ — architecture, API, SDKs (Python, JS, React, Vue), webhooks

docs/install/ — deployment, environment, upgrades, backups

docs/api/ — REST API, OpenAPI, Swagger, Redoc

docs/advanced/ — RAG pipeline (chunking, embeddings, retrieval, reranking)

docs/diagrams/ — architecture, database, RAG, auth, deployment, multi-tenancy

agents.md — IBM Bob 2.0 contract (10 sections)

See also:

ARCHITECTURE.md — system-level overview

ROADMAP.md — what's planned + [Bob-Auto-Fixes]

GLOSSARY.md — platform-specific terminology

🧪 Tests
bash
# Backend tests
pytest tests/ -x

# Eval Lab tests
pytest tests/eval/ -x

# Backend lint
ruff check api/

# Frontend type check
cd frontend && npm run type-check
314 backend test files, all green.

🌍 Internationalization
6 languages: English (default), French, Spanish, German, Portuguese, Arabic

~4,200 translations in locales/

i18n system: custom (frontend/lib/i18n.tsx), backend (api/services/i18n.py)

Selector: frontend/components/LanguageSelector.tsx

📜 License
MIT — see LICENSE.

📚 Project history
Built incrementally across 25 documented development parts, each with its own audit, real (never fabricated) test results, and honest documentation of gaps and limitations.

The full history — including which features were genuinely new vs. extensions of existing infrastructure, every real bug found and fixed, and every deliberate scope decision — is in docs/CAHIER_DES_CHARGES.md.

The project's origin as a single-tenant, hand-evaluated RAG demo, with its own real retrieval-quality measurements and honestly-documented methodology caveats, is preserved at src/README.md.

🤝 Contributing
See CONTRIBUTING.md and CODE_OF_CONDUCT.md. Security issues should be reported per SECURITY.md.

IBM Bob 2.0 Submission — 2026
