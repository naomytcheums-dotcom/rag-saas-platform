# 01 - Project history: from a FastAPI-docs Q&A prototype to a multi-tenant SaaS

Evidence tags as in `00_EXECUTIVE_OVERVIEW.md` ([V] read now, [R] run in the working sessions, [D] stated in repo docs, [U] unknown).

## 0. What could and could not be consulted
| Source | Used? |
|---|---|
| Git history of the repository (653 commits, 2026-08-31 -> 2026-10-12, 20+ branches, no tags) | **Yes** [V] (`git log`, dates and subjects) |
| README, ARCHITECTURE, ROADMAP (4,311 lines), CHANGELOG, HANDOVER (865 lines), AUDIT, `docs/CAHIER_DES_CHARGES.md` (3,898 lines), `docs/DECISIONS.md`, `docs/IBM_BOB_2_SUBMISSION.md`, `agents.md`, `src/README.md`, `bob/README.md` | Yes (read in part; the ROADMAP is far too long to be summarised line by line) |
| Alembic migrations 0001-0143 | Yes [V] (`annex/migrations.csv`) |
| Pull-request pages on GitHub (title, checks) | PR #25 only, through the `gh` command-line tool [R] |
| **History before 2026-08-31** | **[U]** The first commit (`6a5fe03`, "Snapshot: rag-saas-platform (RAG pipeline + Partie 1.1 auth backend)") already contains the RAG pipeline, `api/`, Dockerfile and README. Whatever happened before it (earlier repositories, the original chat where the cahier des charges was written) is not in this repository. `docs/CAHIER_DES_CHARGES.md` itself says the original text "n'existe plus nulle part" and was reconstituted from a pasted message. |
| Earlier chat conversations with AI assistants | Not available as files; only their effects (commits, `docs/ROADMAP`, `docs/HANDOVER`) are. |
| Render, Vercel, Supabase dashboards | **Not accessed.** The README names live URLs (`rag-saas-platform-rho.vercel.app`, `rag-saas-api-sjsm.onrender.com`) [D]. |

Do not trust any date before 2026-08-31, and treat the "origin" below as reconstruction from the artefacts that survive.

## 1. Origin: the "FastAPI docs assistant" (before 2026-08-31) [D/V]
`src/README.md` states that `src/` is "the original, single-tenant RAG pipeline this whole platform grew from": a retrieval-augmented question-answering assistant over the **official FastAPI documentation**, with citations, built as a portfolio project whose selling point was an **honest evaluation methodology**:
* 50 test questions with a target document; Recall@5 88.0 % -> 90.0 % and MRR ~0.79 after a reranker-blend fix; a diagnosis that 5 of 6 misses were caused by the reranker demoting correct results (`results/failure_analysis.md`).
* `AUDIT.md` (a security/quality audit of that codebase) admitted that the reported Recall@5 involved tuning a hyper-parameter on the evaluation set itself - a methodological weakness stated openly.
* Generation was "implemented but blocked on Anthropic API credit" at the time.
* The first UI was **Streamlit** (`.streamlit/config.toml`, root `Dockerfile`, `dashboard/app.py`), deployed with a root `render.yaml` that still declares a service named `nova-fastapi-assistant` (health check `/_stcore/health`, env vars for Anthropic and Google Calendar/Sheets) [V]. That file is a fossil: it describes the prototype, not the SaaS (see 10_TESTS_CI_CD_AND_DEPLOYMENT.md).
Lesson for continuing: the project's culture is *measure, then claim*. Keep that when reporting results.

## 2. Timeline of the platform (from Git) [V]
Commit counts per day: 08-31:2, 09-01:39, 09-02:24, 09-03:20, **09-04:64**, 09-07:35, 09-08:22, 09-09:6, 09-10:12, 09-11:7, 09-12:11, 09-13..14:2 each, 09-15:9, 09-16:8, 09-17:17, 09-18:13, 09-19:16, 09-23:11, **09-24:73**, 09-25:27, 09-26:11, 10-05:21, 10-06:12, 10-07:15, 10-08:11, 10-09:43, **10-10:87**, 10-11:27, 10-12:3.

| Period | What changed | Evidence |
|---|---|---|
| **Aug 31 - Sep 1** | Snapshot commit, then **Part 1.1 (authentication)** built and hardened in one day: real PostgreSQL/Redis/Celery/Resend validation, Row Level Security switched on for all public tables (`0002`), avatar storage on S3-compatible storage, rate limits on the five riskiest auth routes, 2FA recovery codes, GDPR consent tracking, a fixed 2FA bypass via OAuth, revocable access tokens, JWT key rotation, CSRF on refresh/logout. | commits `48b288a`..`1c7ef54`, migrations 0001-0006 |
| **Sep 2-3** | Organizations, members, roles and quotas (Parts 1.2-1.4): per-member limits, per-organization configuration, custom domain with automatic Let's Encrypt (ACME v2), white-label toggle. Knowledge-base imports (Part 2.1): Markdown, sitemap, Google Drive (OAuth refresh-token flow, "no live account to verify against"). | commits of 09-02/03 |
| **Sep 4** (64 commits) | **Agents (Part 5)**: tools (URL reader, GitHub, parallel tool calls, per-agent/per-user tool permissions, cross-session memory), Parts 5.1-5.3 largely built that day. | commits `feat(api): Partie 5.x` |
| **Sep 7-8** | **Citations and anti-hallucination (Part 6)**, workflow blocks (5.4), **Evaluation Lab (Part 7)**: context relevance, citation correctness, hallucination rate, latency/cost metrics, regression detection; the full chat UI assembled "from user testing". | commits 09-07/08 |
| **Sep 9-14** | Integrations (Part 9/15): Zapier/Make/n8n webhooks, Airbyte client, Twilio; Parts 18-23 (sales models, white-label, analytics, A/B testing, multimodal incl. CLIP visual search, autonomous agents); final documentation (Part 25) on 09-14. | commits 09-10..14 |
| **Sep 15-19** | CI stabilised (the giant pytest invocation split into 4 sequential processes to avoid memory kills); **free Celery worker via scheduled GitHub Actions** (09-17) because Render's worker has no free tier and running it inside the web container "OOMed the whole app"; **AI Pack: credits debited per real LLM call + BYOK** (09-17); a critical audit document (09-19); "Crawlix" automated QA reports (09-16, `crawlix-reports/`, `Modelfile.crawlix` = a llama3.2 Ollama profile) [V]. | commits, `.github/workflows/celery-worker.yml` |
| **Sep 23-26** (the **IBM Bob 2.0 contest** period) | Étapes 6-10 (function calling, long-term memory, Production/DevOps, MCP client/server), performance docs, DB-editable notification templates, S3/R2 backups, architecture docs, i18n (6 languages at the time). `agents.md` defines **IBM Bob 2.0 as "Lead AI Systems Engineer"** and four modes (FACTORY, GUARDIAN, AUTOPSY, CHANGELAB); `bob/` and `docs/ibm_bob_2/` hold the contest submission and a measured example (Recall@5 +0.40 on real documents). | commits 09-24..26, `agents.md`, `bob/` |
| **Sep 27 - Oct 4** | Almost no commits (3 on 09-27, none 09-28..10-04). The ROADMAP records a "Hardening Mission" executed in numbered sections (§4 rate limiting, §5 webhook anti-replay, §6 cost control, §9 RBAC, §13 Guardian, §15 A2A, §16 MCP, §29 red team...) and staging missions on 10-03/10-04 (commit dates may lag). | `ROADMAP.md` sections "[Bob-Auto-Fixes]" |
| **Oct 5-8** | Migrations 0125-0132, tenant isolation sweep, authentication of the Teams/Discord gateway webhooks, optional dependency files, language menu with flags, fr/en only (D7), CircleCI MinIO image replaced, production operator checkpoint written in the README (DB at revision 0130, 178 tables, 12 without RLS, zero policies). | commits 10-05..08, README |
| **Oct 9-10** (130 commits) | **Independent functional audit of the 514 features**: billing fixes (back-office cancellation reaches the provider BILL-006; plan limits derived from the subscription BILL-007), missing `notification_templates` migration (TEN-006), RAG task registration so documents are never lost (RAG-002/003), architecture diagrams, `GET /responses/{id}/trace`, four vertical evaluation datasets, Playwright smoke tests, decisions D1-D14. | `audit-reports/functional-audit-2026-10-10/`, `docs/DECISIONS.md` |
| **Oct 11-12** | Tests made hermetic (local disposable stack), **per-organization connector credentials** (D17, migration 0143), prompt-injection second opinion measured (D15), CinetPay chosen as the target payment provider (D16, not built), production migrated to 0143, CircleCI re-architected to 4 parallel containers. PR #25 opened. | commits 10-11/12, PR #25 |

## 3. Structural changes of vision, name and scope
| Change | Before | After | Where it shows |
|---|---|---|---|
| Product shape | Single-tenant Q&A over FastAPI docs | Multi-tenant SaaS (organizations, roles, quotas, billing) | `src/` vs `api/` |
| UI | Streamlit | Next.js 16 / React 19 dashboard + embeddable widget + SDKs | `dashboard/app.py` (legacy) vs `frontend/` |
| Name | "nova-fastapi-assistant" (Render service), "FastAPI docs assistant" | "RAG SaaS Platform" (D3, 2026-10-11); contest name "RAG Evolution Factory" | root `render.yaml`, README, `agents.md` |
| Vector search | In-process NumPy cosine over all chunks of an organization | Native **pgvector HNSW** index (migration 0128) with a NumPy fallback for other dimensions and for SQLite tests | `retrieval_pipeline.py`, `document_chunks.embedding_vector` |
| Languages | 6 UI languages (en, fr, es, de, pt, ar) | **fr, en only** (D7) | `UI_SUPPORTED_LANGUAGES` |
| Tenant isolation | Application filters + RLS enabled with no policy | Same; database barrier explicitly staged, not on (D2/D8) | `docs/DECISIONS.md` |
| LLM billing | Pay your provider | Prepaid credits debited per call, spend caps, BYOK (D13) | `billing_credits.py` |
| Payments | Stripe + Paystack designed (D14) | Both unusable for a Cameroon individual; CinetPay planned (D16) | `billing_providers/` |
| Quality loop | Manual tuning | Eval Lab + Evolution engine + Guardian alerts (the Bob "closed loop") | `rag_evolution_engine.py`, `alerting.py` |
| Connector credentials | One server token for everybody | One encrypted credential set per organization (D17) | migration 0143 |
| Test environment | Real `.env` (production services) | Disposable local stack; `scripts/run_tests_local.sh` blanks hosted and paid keys | `scripts/run_tests_local.sh` |

## 4. Naming of work units (needed to read commits and docs)
* **Partie N.M.K** = a numbered feature of the cahier des charges (Part N, section M, item K). The audit CSV `feature_id` uses the same numbers.
* **Étape / Phase** = a work session unit. **Hardening Mission §N** = numbered section of an internal hardening brief.
* **Bob-Auto-Fixes** = the log format in `ROADMAP.md` mandated by `agents.md` for each automatic fix.
* **D1..D17** = owner/maintainer decisions in `docs/DECISIONS.md`.
* **BILL-###, TEN-###, RAG-###, SADM-###, R-##** = finding identifiers from audits.

## 5. Recent incidents worth knowing (and their status)
| Date | Incident | Resolution |
|---|---|---|
| 2026-10-11 | A tracing test exported a span to the **production** Tempo (hosted observability variables were read from `.env`) | `scripts/run_tests_local.sh` now blanks hosted observability; test forces them off [R] |
| 2026-10-11 | An OpenAPI export script imported the app with production settings and touched the production pooler around 14:25 | Not re-run; owner told to check Supabase logs [R] |
| 2026-10-11 | Two real Anthropic calls from `tests/llm_optin/test_real_llm.py` observed | Paid LLM/embedding/search/voice keys now blanked in the local runner [R] |
| 2026-10-11 | A generated encryption master key was pasted into a chat | Must not be used; generate a new one in the hosting dashboard [R] |
| 2026-10-11 | CircleCI `api-tests` hit the 1 h limit, then the MinIO service container was OOM-killed | Job split over 4 containers in chunks of 20 files (commits `f2c95c0`, `4ca7480`, `c9ef1e6`); final result not yet observed |
| 2026-10-10 | The first audit-pass test runs had 25 skipped tests because PostgreSQL, S3 and the Celery worker were not provided | Reran with the services: 143 passed, 1 skipped [R] |

## 6. What the history tells a newcomer
1. The platform was built **breadth-first and very fast** (about 1,000 routes in six weeks) by a human directing AI assistants; the code is heavily commented with "real/honest" narration, which is a style, not evidence of correctness.
2. **Claims of completion were repeatedly wrong and then corrected** (e.g. "customers bring their own connector credentials" was false until D17; "off by default" for injection detection was false for factory-built agents). Prefer executed evidence over any status word in a document, including this one.
3. The remaining risk is concentrated in *integration with the real world* (payments, e-mail, OAuth apps, worker in production, monitoring), not in missing features.
