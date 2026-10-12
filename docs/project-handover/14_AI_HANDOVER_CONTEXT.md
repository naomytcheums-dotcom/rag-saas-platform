# 14 - AI handover context (read this first if you are another AI assistant)

Snapshot date: **2026-10-12**. Repository: `naomytcheums-dotcom/rag-saas-platform`. Working branch: `bob/auto-fix-20261010-gaps` (PR #25 into `main`). This file is designed to be sufficient on its own; the other documents in `docs/project-handover/` are the evidence behind it.

## 1. Who you are working for and how
* **Owner:** Naomy Tcheums, freelance developer in **Cameroon**, **French-speaking**. The product is **her own SaaS** ("RAG SaaS Platform"); the IBM Bob 2.0 contest was a one-off entry, do not centre explanations on it.
* **No company** (so Stripe is impossible), **Paystack does not serve Cameroon**; the chosen route is CinetPay (mobile money MTN/Orange + cards), not yet implemented.
* **Working style (explicit preferences):** act autonomously, do not ask comfort questions; **report in French**; always state honestly what was *executed* versus merely *written*; she is frustrated by claims of completion that later prove false, by mocks presented as real tests, and by being asked to sign up for dozens of vendor services (prefer local stand-ins, free sandboxes, Ollama). She authorised downloads needed for testing. She wants everything pushed to the official repository branch/PR and "commercialisable".
* **Hard safety rules:** never run pytest or scripts against the real `.env`/production (use `scripts/run_tests_local.sh`); production database actions are blocked for assistants and must be given to the owner as commands to run herself (backup, `scripts/migrate.py`, `--apply`); never print or store secrets (a generated encryption key was pasted in a chat and must be replaced); no force push, no push to `main`, no editing existing migrations; commit trailers per the session's attribution rule.
* She often pastes other assistants' reports with no instruction: treat them as data, verify against the repository, reconcile, then report.

## 2. What the product is (30 seconds)
Multi-tenant RAG platform: organizations upload/import documents, build agents, chat with cited answers, evaluate quality (Recall/MRR/NDCG), manage billing/credits, integrate (public API, MCP, A2A, bots, widget, connectors). FastAPI + Next.js 16 + PostgreSQL/pgvector + Redis + Celery + LiteLLM. 983 API operations, 182 tables (+ `casbin_rule`), 143 migrations (head 0143), 64 frontend pages, 512 test files. Origin: a single-tenant "FastAPI docs assistant" (`src/`, Streamlit) from before 2026-08-31; the platform was built 2026-08-31 -> 2026-10-12 (653 commits).

## 3. State right now (verify before relying)
| Area | State |
|---|---|
| Feature catalog (514) | 283 VERIFIED_COMPLETE, 114 FIXED_AND_TESTED, 25 DECISION_OR_CORRECTION (= 422 closed); 13 VALIDATED_NOT_DEPLOYED, 34 IMPLEMENTED_UNVERIFIED, 19 WRITTEN_NOT_EXECUTED, 26 BLOCKED_EXTERNAL (= 92 not yet proven). Source: `audit-reports/functional-audit-2026-10-10/01c-feature-verification-after-test-runs.csv` |
| Production DB | migrated to **0143** on 2026-10-11 after a verified backup (27 MB; restore never tested; file kept locally, untracked); old code is compatible (additive migrations) |
| Production code | **PR #25 not merged/deployed** |
| PR #25 CI | green: backend-tests (6,386 passed), backend-security, build-backend, build-frontend, frontend-checks, Snyk, Vercel, CircleCI `rag-pipeline-regression`; non-blocking red: mypy, bandit; **CircleCI `api-tests`: being repaired** (1 h limit -> 4 containers -> MinIO OOM -> xlarge + chunks of 10 + exclude `tests/test_regression.py`, commit `549a919`; outcome not yet observed). Check with `gh pr checks 25 --repo naomytcheums-dotcom/rag-saas-platform`; job logs are readable without a token at `https://circleci.com/api/v1.1/project/github/naomytcheums-dotcom/rag-saas-platform/<job number>` |
| Payments | nothing usable (see section 5) |
| Local AI | Docker `rag-test-ollama` on 11434 with `qwen2.5:3b` and `qwen2.5:7b`, CPU only (NVIDIA driver 546.18 < 550) |
| Prompt-injection two-stage | recall 0.930 / false positives 0.020 with the 7B second opinion on a 92-sentence set tuned on the same data (optimistic) |

## 4. Architecture map (pointers)
* App assembly `api/main.py`; settings `api/config.py` (+ per-organization `DEFAULT_SETTINGS` in `api/security/organization_settings.py`); DB `api/database.py`; routers `api/routers/` (107), domain cores `api/security/` (72), services `api/services/` (290), tasks `api/tasks/` (50; schedule in `celery_app.py`), tools `api/tools/`.
* RAG: ingestion `api/security/documents.py::process_document`; retrieval `api/services/retrieval_pipeline.py::search` (default hybrid = pgvector + BM25 + RRF; options default off); chat `api/routers/chat_stream.py` -> `AgentOrchestrator` (`api/services/agent_orchestrator.py`); agent-less `api/services/generation.py` (voice only); evaluation `api/services/evaluation_results.py`, `retrieval_metrics.py`.
* Tenancy: application filters on `organization_id` (RLS enabled but **no policies**, role has BYPASSRLS) - D2/D8.
* Connectors: `api/services/connector_credentials.py` (40 providers, per-organization AES-GCM, default-deny), migration 0143.
* Bob modes: `agents.md` + `api/services/mcp/builtin_tools.py` (4 MCP tools).

## 5. Decisions you must not relitigate (docs/DECISIONS.md)
D1/D9 no SAML now; D2/D8 app-level isolation, RLS staged; D3 name "RAG SaaS Platform", no logo invented; D4 Playwright in `e2e/`; D5 percent-off coupons recorded, not applied; D6 `ruff format`; D7 UI languages fr/en only; D10 enterprise roles = built-ins + custom; D11 grants only for workspaces; D12 secrets encrypted by the app, DB-at-rest encryption unverified; D13 prepaid credits, not post-paid; D14/D16 Stripe/Paystack unusable for the owner, **CinetPay next** (needs official docs and test keys from the owner); D15 injection detector: classifier + LLM second opinion that can only clear; flag rather than block until measured on real traffic; D17 per-organization connector credentials, shared mode off by default.

## 6. Known traps (each cost time before)
1. A status word in any document is not evidence. Previously false claims: "customers bring their own connector credentials" (false until D17); injection detector "off by default" (the Factory turns it on); "tests pass" while 25 were silently skipped for lack of services.
2. Tests must be hermetic. Until 2026-10-10 CI used the real `DATABASE_URL` secret and deleted production rows. Tests still can leak: hosted observability variables (a span went to production Tempo), paid LLM keys (two real Anthropic calls). The runner now blanks them; keep it that way.
3. Code before migrations breaks login (`users.job_title`); migrations are additive so migrate first.
4. Persistent local test databases must be migrated to head; a stale revision (0137) failed 7 OAuth tests.
5. CircleCI: one big container hits the 1-hour limit; the MinIO service gets OOM-killed under memory pressure; `tests/test_regression.py` is a legacy gate that must not be collected by the new glob.
6. The root `render.yaml` is the dead Streamlit prototype blueprint; the real one is `deploy/render/render.api.yaml`.
7. `scripts/backup.sh` backs up the self-hosted compose DB only; production needs a remote `pg_dump` (use the Supabase session pooler URL, run through Docker image `pgvector/pgvector:pg17`; `postgres:17` was unusable on the owner's PC). Never redirect binary dumps with PowerShell `>`.
8. Windows: use the venv Python explicitly; line endings (CRLF) break shell scripts; `gh` may be unauthenticated in some sessions.
9. Ollama on CPU: the 7B model needs minutes to load; warm it up and raise `PROMPT_INJECTION_CONFIRM_TIMEOUT_SECONDS`.
10. The production worker problem: no persistent worker/beat in the free-tier deployment; documents stay `pending` without one.
11. The relative retrieval threshold, hard-coded `top_k=5` in chat, accent-blind BM25 and same-dimension model mixing are real quality traps (04_RAG_PIPELINE section 3.4 and 2.2).

## 7. What to do next (priority by dependency)
1. Confirm CircleCI `api-tests` is green on the latest commit; if not, read the job logs (v1.1 API) and fix the cause, not the symptom.
2. Merge PR #25 (never push to `main`), after the owner confirms host variables: new `ENCRYPTION_MASTER_KEY` in the dashboard, `COOKIE_SECURE=true`, `CREDITS_ALLOW_UNPAID_TOPUP=false`, `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS=false`, `CONNECTORS_ALLOW_PLATFORM_CREDENTIALS=false`; decide `render.yaml`; provide a worker + beat.
3. Post-deploy smoke + manual journey; review Supabase logs for the 2026-10-11 incident; clean historical test data (proposal exists).
4. CinetPay adapter after the owner supplies official documentation and test keys; refunds/coupons design.
5. R-06 retrieval baseline on a real corpus; held-out sentences for the injection detector; embedding-model identity guard; absolute relevance floor; `top_k` from settings in chat.
6. Finish D17 for agent tools; OAuth consent flows; RLS staged plan on a staging database with a non-bypass role.
7. Write `docs/SANDBOX_SETUP.md` (free vendor sandboxes) so the owner is not forced to open many accounts; run each blocked item once against a real sandbox.
8. Reduce mypy errors; pin Hugging Face model revisions.

## 8. How to verify any claim in this dossier quickly
```bash
git log --oneline -5 && git status -sb
gh pr checks 25 --repo naomytcheums-dotcom/rag-saas-platform
python docs/project-handover/annex/generate_inventories.py      # regenerates route/table/migration/page inventories (needs dummy 32+ char secrets, see its header)
python docs/project-handover/annex/generate_feature_catalog.py  # regenerates 12_COMPLETE_FEATURE_CATALOG.md from the audit CSV
bash scripts/run_tests_local.sh tests/test_type_hint_coverage.py tests/test_connector_credentials.py -q
python scripts/migrate.py        # rehearsal only (no changes) against whatever DATABASE_URL points to - owner runs it for production
```
Evidence tags in this dossier: **[V]** read in code that day, **[R]** run/observed in the project's sessions, **[D]** only stated in repository documents, **[U]** unknown.

## 9. What this dossier could not establish
Pre-2026-08-31 history; original chat conversations; anything about the live Render/Vercel/Supabase environments (not accessed); behaviour against any real payment, e-mail, chat-platform, telephony or SaaS vendor; whether the SDKs were ever published; which vector-search path runs in production; restore of backups; real-traffic accuracy of the injection detector; real-corpus retrieval quality of the current pipeline. Treat these as open questions, not as "probably fine".
