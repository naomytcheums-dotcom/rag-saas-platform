# 10 - Tests, CI/CD and deployment

Tags: **[V]** read in repository files 2026-10-12; **[R]** executed/observed during project sessions (including `gh` queries of PR #25); **[D]** documented only; **[U]** unknown / not accessed. **Hosting dashboards (Render, Vercel, Supabase), DNS and certificates were never accessed from the working environment**; everything about the hosted state is documented intent or owner-reported.

## 1. What "tested" means here (never merge these levels)
| Level | Meaning | Example in this project |
|---|---|---|
| Written | a test file exists | 512 files, 5,604 test functions (6,386 cases with parametrisation in the last full CI run) |
| Run locally | passed in the disposable local stack | Parts 1-15 of the audit, 143 passed for Part 13 with PostgreSQL/S3/Celery [R] |
| Passed in CI | GitHub Actions `backend-tests` (SQLite default fixtures + a disposable pgvector PostgreSQL + Redis + MinIO for the integration files) | 6,386 passed [R] |
| Passed against real services | ClamAV daemon, Jaeger collector, pgvector HNSW, Ollama LLM, Celery worker, S3 (MinIO), Tesseract OCR | each has a dedicated test that passed [R] |
| Passed against a vendor | Stripe, Paystack, Resend, Slack/Teams/Discord, Twilio, Drive/Notion/Jira/... with real accounts | **none** (mock/fake transports only) |
| Passed in production | `scripts/post_deploy_smoke.py` / manual journey against the live URLs | **never recorded** [U] |
A passing unit test says nothing about production; an applied migration says nothing about business flows.

## 2. Test suites
### 2.1 Backend (`tests/`, pytest + pytest-asyncio)
* Default DB fixture = in-memory **SQLite** (fast; `Vector` degrades to JSON). PostgreSQL-only behaviour (pgvector operators, RLS, `FOR UPDATE`, triggers) is tested by dedicated files with their own fixtures (`tests/test_postgres_integration.py`, `test_rbac_integration.py`, `test_pgvector_real_search.py`, concurrency tests) that need `TEST_DATABASE_URL`.
* **Isolation rule (since 2026-10-10):** `tests/conftest.py` refuses to start if `DATABASE_URL`, Redis or S3 point to a remote host. Before that date the GitHub job used the repository secret `DATABASE_URL`, i.e. **the real database, and integration tests read and deleted rows there** (recorded in `.github/workflows/ci.yml` comments). Never run pytest with the real `.env`; use `scripts/run_tests_local.sh`, which exports a local `DATABASE_URL` (default `postgresql+asyncpg://postgres:postgres@localhost:15432/rag_saas_test`), local Redis and S3, blanks Stripe/Paystack, hosted observability (Loki, Tempo, Langfuse, Sentry, alert webhook, OTLP endpoint) and, since 2026-10-11, **every paid LLM/embedding/search/voice key**.
* Notable suites: auth/security (hundreds of tests), route classification, viewer-role matrix, tenant isolation, IDOR, SQL-tool bypass, SSRF and outbound-HTTP inventory (`test_outbound_http_inventory.py`), workflow code-block hardening, prompt-injection (`test_prompt_injection_second_opinion.py`, optional measured test `test_prompt_injection_measured.py` needing `PROMPT_INJECTION_MEASURE=1`), connector credentials (38), real-service tests (ClamAV, tracing, pgvector, Celery e2e lifecycle), documented-endpoint contract test, type-hint ratchet (`test_type_hint_coverage.py`, floor 69.0 %, current 69.1 % after the 2026-10-11 annotations), CI timeout guard, opt-in `tests/llm_optin/` (real Ollama: 11 passed on 2026-10-11 [R]; hosted LLM tests require explicit env and cost money).
* Known harness subtleties: the lifecycle test needs a private worker/Redis (another session's worker answering on a shared Redis broke the purge count); persistent test databases must be migrated to head after new migrations.
### 2.2 Frontend
Vitest + Testing Library (`frontend/**/*.test.tsx`), ESLint, `tsc --noEmit` ("type-check"). Playwright smoke tests in `e2e/` (own package; 12/12 in Chrome [R]; nightly workflow).
### 2.3 SDKs and pipeline
`sdks/python/tests`, `sdks/js/tests`, vitest for React/Vue SDKs (not part of the main CI [U]); `tests_pipeline/` + `tests/test_regression.py` + `results/regression_baseline.json` = the legacy single-tenant retrieval regression gate (CircleCI job `rag-pipeline-regression`).
### 2.4 Other test types
Load test script (`scripts/loadtest.py`) and `docs/PERFORMANCE_REPORT.md` (a 2026-10 benchmark found and fixed two bottlenecks; reranker section added); retrieval benchmarks (`retrieval_benchmark*.py`; the HNSW 100/1000/10000-document measurement was "in progress", i.e. not a claim); staging validation scripts (`staging_validate.py`, `staging_journeys.py`; no authenticated staging session was ever established); chaos/failure injection: none found.

## 3. CI/CD
| System | Workflow / job | Trigger | Blocking? | What it does |
|---|---|---|---|---|
| GitHub Actions | `ci.yml`: `backend-tests`, `backend-security`, `build-backend`, `build-frontend`, `frontend-checks` | push to `main`, PR to `main` | yes | pytest with pgvector/Redis/MinIO services (75-minute timeout, ~41 min measured), pip audit, Docker build of `Dockerfile.api`, Next.js build, lint/type-check/unit tests/npm audit |
| GitHub Actions | `mypy.yml`, `bandit.yml` | push/PR | **no** (`continue-on-error`) | type check (many errors), security lint (5 Hugging Face alerts) |
| GitHub Actions | `e2e.yml` | nightly 03:17 + manual | no | Playwright |
| GitHub Actions | `celery-worker.yml` | every 10 minutes | n/a | burst Celery worker (12-minute job) draining the Redis queue - the zero-cost stand-in for a worker service |
| GitHub Actions | `migrate.yml`, `post-deploy-smoke.yml`, `llm-tests.yml` | manual | n/a | run migrations, smoke the live URLs, run real-LLM tests |
| CircleCI | `rag-pipeline-regression` | push | status check | legacy retrieval unit tests + rebuild of the FastAPI-docs vector store + regression gate |
| CircleCI | `api-tests` | push | status check | full backend suite on **4 parallel containers** (as of commit `549a919`: xlarge, chunks of 10 files, one pytest process per chunk, each container with its own pgvector/Redis/MinIO/Celery worker) |
| Vercel | preview + production builds of the frontend | push | status | deployment checks appear on the PR |
| Snyk | dependency/code scan | PR | status | passes |
No branch protection on `main` was found (`gh api .../branches/main/protection` -> 404), so required-check enforcement is by convention only [R].

### 3.1 CircleCI `api-tests` history on 2026-10-11/12 [R]
| Run | Result | Cause found |
|---|---|---|
| single container, 4 hand-listed batches | **timed out at 1 h 00** (and earlier exit 137) | suite of 6,300+ tests no longer fits the 1-hour job limit in one container |
| 4 containers, one pytest per container (`f2c95c0`) | container 1: MinIO service OOM-killed (exit 137), then 1 failure + 6 errors in S3 tests; container 3 stopped | memory piled up in a long process |
| 4 containers, chunks of 20 (`c9ef1e6`; run 599) | containers 0 and 1 passed; container 2: MinIO OOM-killed at ~5 min on `large`; container 3: **`ERROR tests/test_regression.py`** (legacy file collected by the new glob) while 6 chunks passed | memory + a file the old hand lists never included |
| 4 containers, xlarge, chunks of 10, `test_regression.py` excluded (`549a919`) | **result not observed when this was written** | |
Cost note: xlarge uses twice the credits per minute of large; with 4 containers a run is a few thousand credits. If credits are scarce, GitHub's `backend-tests` runs the same suite and is the primary gate. Coverage: the previous `--cov-fail-under=75` gate (batch 4 only) is no longer evaluated; `coverage.xml` is stored per container as an artifact.

### 3.2 Pull request #25 [R]
* Title area: "Gaps": branch `bob/auto-fix-20261010-gaps` -> `main`; **168 files changed, +8,421 / -370, 42+ commits** (the first on 2026-10-10 21:33 UTC). Content: functional-audit fixes (invoice/cancellation/SADM fixes, RAG task registration, observability trace endpoint, verticals datasets), D1-D17 decisions, hermetic test infrastructure, workflow code-block hardening, escalation webhook SSRF protection, per-organization SLA, latency-metrics fix, pgvector real-search test, ClamAV and tracing real-service tests, prompt-injection two-stage design and measurements, **per-organization connector credentials with migration 0143**, LLM provider error mapping (`llm_providers.py`), CI repairs, documentation (runbook, resume prompts), type annotations to keep the ratchet, CircleCI re-architecture.
* **Checks at last observation (commit `c31b178`):** green: `backend-tests`, `backend-security`, `build-backend`, `build-frontend`, `frontend-checks`, Snyk, Vercel (2), CircleCI `rag-pipeline-regression`; red but non-blocking: `mypy`, `bandit`; **red: CircleCI `api-tests` (run 599, causes listed above; fix `549a919` pushed, outcome unobserved)**.
* **Merge/deploy status:** **not merged**. The production database was already migrated to 0143 on 2026-10-11, which is safe for the old code (additive). Merging `main` triggers the hosting auto-deploy if configured [U].

## 4. Environments
| Environment | Description | State |
|---|---|---|
| **Local dev** | Python 3.13 venv, `uvicorn api.main:app`, Next dev server, Docker for PostgreSQL/Redis/MinIO | see section 5 |
| **Local disposable test stack** | containers `rag-test-pg` (pgvector 17, port 25432 or 15432), `rag-test-redis` (+ `-b` private), `rag-test-minio`, `rag-test-clamav`, `rag-test-jaeger`, `rag-test-ollama` (11434, models `qwen2.5:3b`, `qwen2.5:7b`; CPU only because the NVIDIA driver 546.18 is older than the 550 needed by the current Ollama image) | running on the owner's PC |
| **CI** | GitHub-hosted runners with service containers; CircleCI Docker executors | working except the item above |
| **Staging** | an owner-provided Supabase staging project existed; IPv6-only host unreachable from the working environment | never authenticated [U] |
| **Production** | frontend Vercel `rag-saas-platform-rho.vercel.app`; API Render `rag-saas-api-sjsm.onrender.com`; database Supabase (revision 0143 after 2026-10-11); worker/beat: **burst worker via GitHub Actions only, beat not running** unless the paid blueprint was applied [U]; Redis and storage providers [U]; custom domain and TLS [U] | owner-reported/documented; not accessed |
### 4.1 `render.yaml` (root) vs `deploy/render/render.api.yaml`
Root `render.yaml` = the Streamlit prototype blueprint (service `nova-fastapi-assistant`, Dockerfile root, free plan, health path `/_stcore/health`, Anthropic + Google Calendar/Sheets variables). If a Render **Blueprint** is linked to the repository, Render reads this file automatically and could try to create that obsolete service. `deploy/render/render.api.yaml` is the real blueprint: web `rag-saas-api` (standard plan; "the free 512 MB plan cannot hold the ML dependencies plus a worker"), worker `rag-saas-worker` (standard), beat `rag-saas-beat` (starter), cron `rag-saas-maintenance` (starter). Decide before merging whether the root file is replaced or deleted.
### 4.2 Consequences of a missing Celery worker (production)
`POST /documents` stores the file and enqueues; without a worker the document stays `pending`, never becomes searchable; URL/sitemap/GitHub/Drive/Notion imports never run; evaluation and comparison jobs, workflow runs, notification e-mails with retries, account purge and retention sweeps, monthly invoices and credit grants, alert rules, reindex schedules and media backfills do not run. The 10-minute burst worker covers queued one-off tasks with a delay of up to 10 minutes but **not beat-scheduled tasks** (no beat process) - so retention, invoicing and alerting need the paid beat/worker or a separate scheduler. The web process also has `requeue-stale-pending-documents`, which needs beat to run.

## 5. Running the project locally (commands present in the repo)
Prerequisites: Python 3.13, Node 20+ (Next 16), Docker, PostgreSQL with pgvector, Redis; optional Tesseract/poppler, ClamAV, Ollama.
```bash
python -m venv venv && source venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-api.txt -r requirements-optional.txt
cd frontend && npm install && cd ..
# database + redis (disposable examples, see scripts/run_tests_local.sh header)
docker run -d --name rag-test-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=rag_saas_test -p 15432:5432 pgvector/pgvector:pg16
docker run -d --name rag-test-redis -p 16379:6379 redis:7-alpine
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:15432/rag_saas_test
alembic upgrade head
uvicorn api.main:app --reload --port 8000               # API
celery -A api.tasks.celery_app worker --loglevel=info   # worker (Windows: separate beat process, no -B)
celery -A api.tasks.celery_app beat --loglevel=info     # scheduler
cd frontend && npm run dev                              # UI on :3000 with NEXT_PUBLIC_API_URL=http://localhost:8000
```
Required settings (names only): `DATABASE_URL`, `JWT_SECRET_KEY` and `SESSION_MIDDLEWARE_SECRET` (>= 32 chars), `AUDIT_LOG_HMAC_SECRET_KEY`, `SUPPORT_EMAIL`, `REDIS_URL`/`RATE_LIMIT_REDIS_URL`, S3 variables, an LLM provider key or `OLLAMA_BASE_URL`, `RAG_ENV_FILE` to choose a dotenv file. Self-hosted production-like stack: `docker-compose.selfhosted.yml` (postgres, redis, api, celery-worker, celery-beat, frontend, nginx, certbot); observability: `docker-compose.observability.yml` (Loki, Prometheus, Tempo, Jaeger, OTLP collector, Grafana, n8n). Installers: `install.sh`, `update.sh`, `uninstall.sh`.
Tests: `bash scripts/run_tests_local.sh tests/<file>.py -q` (never plain `pytest` with the real `.env`); lint `ruff check api/`, `ruff format api/`; frontend `npm run lint`, `npm run type-check`, `npm test`; e2e `cd e2e && npm install && npx playwright test`.
Diagnostics: `scripts/check_env_ready.py`, `scripts/check_optional_deps.py`, `scripts/post_deploy_smoke.py --api <url> --frontend <url>`, `/health`, `/metrics`, `GET /responses/{id}/trace`, `ROADMAP.md` troubleshooting.

## 6. Release procedure (proven pieces in `docs/RELEASE_RUNBOOK_2026-10-11.md`)
Backup -> migration rehearsal -> `--apply` -> set environment variables -> merge PR -> deploy -> smoke -> manual journey. Done on 2026-10-11: backup (custom-format `pg_dump`, 27 MB, verified with `pg_restore --list`; restore never tested), rehearsal passed, apply to 0143. **Pending:** `ENCRYPTION_MASTER_KEY` (new), `COOKIE_SECURE=true`, `CREDITS_ALLOW_UNPAID_TOPUP=false`, merge, deploy, smoke, worker/beat decision.
`scripts/backup.sh` backs up the **self-hosted compose database only**.

## 7. Infrastructure as code
Helm chart (`deploy/helm/rag-saas`), Kubernetes manifest, Terraform for AWS/GCP/Azure/DigitalOcean, Fly and Railway files, dedicated-tenant provisioning (`deploy/dedicated-tenant`). All were validated with the official tools (`terraform validate`/`fmt`, `helm lint`, `kubeconform`, `shellcheck`, `actionlint`, `docker compose config`) and one Azure `for_each`-over-sensitive-map error was fixed; **none was ever applied to a real account or cluster** (status VALIDATED_NOT_DEPLOYED, 13 features).
