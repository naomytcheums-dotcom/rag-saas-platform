# RAG SaaS Platform

**A multi-tenant platform for building, evaluating and operating retrieval-augmented (RAG) assistants on your own documents — with verifiable citations, strict tenant isolation, built-in cost control, and a quality loop that measures every change instead of guessing.**

🌐 **Live app**: https://rag-saas-platform-rho.vercel.app
🔧 **Live API**: https://rag-saas-api-sjsm.onrender.com

---

## What it is

An organization signs up, uploads documents (or connects its sources), configures one or more assistants, and gets:

- answers grounded in **its own documents**, each with citations to the exact source chunk;
- a hard **isolation boundary** between customers (every query, cache key, job and trace is organization-scoped);
- **guard rails on spend** (credit balance, daily/monthly caps, per-organization rate limits, bring-your-own-key);
- an **evaluation lab** that scores retrieval and answers with real metrics, so a configuration change is accepted only if the numbers improve.

It is designed to be self-hosted (Docker) or run as a SaaS.

---

## Capabilities

### Retrieval
- Native **pgvector** search with an HNSW index on PostgreSQL (with a dimension-safe in-process fallback for other embedding sizes and for the SQLite test suite)
- Hybrid retrieval: dense vectors + BM25, fused with Reciprocal Rank Fusion; optional cross-encoder reranking
- HyDE, multi-query, query rewriting, MMR diversification, context compression, metadata filtering
- **Policy-aware retrieval** (OPA/Rego, opt-in): permissions are applied at search time, not only at display time
- **Multimodal**: images (OCR, vision description, YOLOv8 object detection, CLIP text↔image search), audio and video (transcription, frame description)
- GraphRAG (LightRAG) and long-term agent memory (mem0), with per-document / per-organization deletion for GDPR

### Agents and integrations
- Configurable agents (prompt, tools, knowledge base, guardrails) and autonomous agents with bounded multi-step loops and human approval
- **MCP**: the platform is both an MCP client (external tool servers, behind a firewall with policy, SSRF protection and audit) and an MCP server (its own tools, per-organization API keys)
- **A2A (Agent2Agent)**: each organization can expose its RAG agent to external A2A-compliant agents (agent card + JSON-RPC), authenticated and cost-controlled
- Workflows (Celery), webhooks, 30+ connectors, embeddable chat widget, public `/v1` API with Python / JavaScript / React / Vue SDKs, SSE streaming

### Quality loop
- **Eval Lab**: datasets, jobs, per-question results, Recall@k, MRR, NDCG, precision, hallucination rate, latency and cost
- **Evolution engine**: proposes a configuration change, measures it against a baseline, recommends it only on a real measured gain
- **Guardian**: per-organization alerts when retrieval quality (e.g. Recall@5, MRR, NDCG, hallucination rate) drops below a threshold
- **Autopsy**: failure reports grouped by cause (retrieval / generation / hallucination), tenant-scoped
- Flight recorder: every answer carries the strategy, embedding model, provider and model that produced it

### Security and governance
- Multi-tenant RBAC (owner / admin / manager / member / viewer + custom roles); JWT, TOTP 2FA, WebAuthn, persistent account lockout
- Prompt-injection detection on the question **and** on retrieved content
- SSRF-safe outbound HTTP everywhere; secrets encrypted at rest (AES-256-GCM); audit logs
- Per-organization rate limiting on every costly surface; atomic idempotency for payment webhooks (Stripe, Paystack)

### Business
- Credits, subscriptions, invoices, quotas, BYOK; Stripe and Paystack
- White-label (branding, custom domains, SSL), analytics, admin console, plugin marketplace, 6 UI languages (EN, FR, ES, DE, PT, AR)

---

## Stack

| Layer | Choice |
|---|---|
| API | FastAPI (Python 3.11), SQLAlchemy 2.0 async, Alembic |
| Data | PostgreSQL (Supabase) + pgvector, Redis |
| Jobs | Celery + Redis |
| LLM access | LiteLLM — Anthropic, OpenAI, Mistral, Gemini, Ollama, watsonx, any OpenAI-compatible endpoint |
| Frontend | Next.js 16, React, TypeScript, Tailwind |
| Observability | Prometheus, Grafana, Sentry |

Snapshot measured on 2026-10-03: 100 router modules, 936 registered API
operations (781 OpenAPI paths), 132 Alembic migration files and 177 ORM
tables and 399 Python test files. These are local source/metadata counts, not a deployed database
inventory. See [autonomous discovery](docs/AUTONOMOUS_AUDIT_01_DISCOVERY.md)
for the file inventory and [final status](docs/FINAL_STATUS.md) for executed
tests and unresolved blockers.

Staging verified on 2026-10-04 (Supabase project `<STAGING_PROJECT_REF>`,
not local Docker): Alembic **0132**, **178 public tables** including
`alembic_version`, pgvector **0.8.2**, and the chunk HNSW index.
The revision was also verified visually in Supabase Table Editor.
The local API connected to this staging reports database/rate-limit Redis/cache
readiness OK. Two browser-created users and organizations successfully logged in;
cross-organization reads returned 404 in both directions.
Nine representative staging IDOR tests passed using these same tenants
(zero skips). These are bounded authentication/authorization checks, not
exhaustive tenant-isolation or RLS certification.
See [staging evidence and reproduction](docs/audit/STAGING_TEST_REPORT.md).

---

## Getting started

### Self-hosted (Docker)

```bash
git clone https://github.com/naomytcheums-dotcom/rag-saas-platform.git
cd rag-saas-platform
cp .env.example .env        # then fill in the secrets
./install.sh
docker compose -f docker-compose.selfhosted.yml up -d
```

### Local development

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements-api.txt
alembic upgrade head
uvicorn api.main:app --reload
cd frontend && npm install && npm run dev
```

---

## Documentation

Start at [docs/index.md](docs/index.md).

| Topic | Where |
|---|---|
| Architecture | [ARCHITECTURE.md](ARCHITECTURE.md), [docs/architecture/](docs/architecture/) |
| API reference | [docs/api/](docs/api/) |
| Deployment | [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) |
| Terminology | [GLOSSARY.md](GLOSSARY.md) |
| Roadmap and the dated log of every fix | [ROADMAP.md](ROADMAP.md) |
| Product requirements and history | [docs/CAHIER_DES_CHARGES.md](docs/CAHIER_DES_CHARGES.md) |

---

## Testing

```bash
pytest tests/ -x
pytest tests/ --cov=api --cov-report=term-missing
cd frontend && npm run lint && npm run type-check
```

The suite is large and loads real embedding / vision models; on a machine with limited RAM run it in sequential batches (one pytest process per group of files) rather than as a single process. Tests that need an external provider (Stripe, Paystack, Google Drive, a real Tesseract binary, …) skip themselves when it is not configured — they are reported as skipped, never as passed.

Every behavioural fix is recorded in [ROADMAP.md](ROADMAP.md) with its test and what was actually executed, including what was written but not yet run.

---

## Status and known limits

This section is deliberately explicit:

- **Staging is connected and migrated:** Supabase session pooler, revision
  0132, 178 public tables, pgvector 0.8.2 and HNSW. 77 policies target a
  restricted lab role; live A/B document RLS and representative API IDOR
  checks pass (11/11). Runtime API/worker still use a bypass role, so this
  is not application-wide DB isolation certification.
  See [staging report](docs/audit/STAGING_TEST_REPORT.md).
- **Latest full backend run (2026-10-04):** 5,408 tests collected,
  5,354 passed, 54 skipped, 0 failed, 23 deselected; 10,680.761 seconds
  with `.venv`. Run started at 20:51:26 and ended at 23:49:27 local time.
  The 54 skipped integration checks and 23 deselected tests are not
  certified. Frontend: 116/116 passed, type-check passed, lint zero errors
  and warnings.
  See [individual failure register](docs/audit/BACKEND_FAILURE_REGISTER.md)
  and [current final status](docs/FINAL_STATUS.md). Earlier backend counts
  are retained in dated historical entries, not current results.
- **Load testing is partial.** `scripts/retrieval_benchmark.py` measured the portable (non-pgvector) retrieval path at 100 and 1,000 documents (see ROADMAP.md for the numbers and the fixes they drove). It does not yet cover 10,000 documents, the PostgreSQL pgvector/HNSW path, or the HTTP layer under concurrent users. Keyword (BM25) search is still computed per query over the organization's chunks, so very large corpora need a persistent full-text index (planned, requires a migration).
- **Guardian** raises and records quality alerts; the full detect → explain → propose → approve → apply → roll back loop is not automated end to end.
- **A2A** is non-streaming, without push notifications; task credits are a flat estimate because the underlying agent does not expose token usage.
- Features that depend on an external provider (voice, fine-tuning, payments, SSO, OPA server, third-party MCP servers) require configuration and deployment-specific validation; their presence in the source is not a proof that a configured provider works in production.

---

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report vulnerabilities as described in [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).

---

*History: this project was once entered in the IBM Bob 2.0 contest; that material is preserved in [docs/ibm_bob_2/CONTEST_README.md](docs/ibm_bob_2/CONTEST_README.md).*
