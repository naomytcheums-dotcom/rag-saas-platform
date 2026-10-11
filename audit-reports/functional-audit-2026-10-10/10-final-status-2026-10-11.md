# 10 - Final status (2026-10-11)

Built by `build_final_status.py` from `01c-feature-verification-after-test-runs.csv` (column `status_final`); nothing here is typed by hand except the prose.

## Result on the 514 features

| Status | Count | Meaning |
|---|---:|---|
| VERIFIED_COMPLETE | 283 | reviewed as complete and its Part test run is green; no fix was needed |
| FIXED_AND_TESTED | 109 | a gap was found, fixed, and the fix is covered by tests that ran green (the fix_evidence column says what was not run against a real provider) |
| VALIDATED_NOT_DEPLOYED | 13 | checked with the official tool (terraform validate, helm lint, kubeconform, shellcheck, actionlint, docker compose config) but never applied to a real account, cluster or workflow run |
| DECISION_OR_CORRECTION | 23 | an owner decision is recorded, or the first assessment was wrong; nothing left to build |
| WRITTEN_NOT_EXECUTED | 19 | code or documents exist; nothing proves them yet |
| IMPLEMENTED_UNVERIFIED | 39 | implemented, but the reviewer could not call it complete from the code and its Part tests alone (gap listed per item) |
| BLOCKED_EXTERNAL | 26 | cannot be proven without an account, key or service that is not available here |
| AMBIGUOUS_REQUIREMENT | 2 | the requirement has no testable acceptance criterion |

Rule: a feature is VERIFIED_COMPLETE only if the code review judged it complete AND the targeted tests of its Part ran green. The unit of proof is the Part, not the sentence of each requirement.

## Test runs (all 15 Parts have a recorded run)

| Part | Result | Detail |
|---|---|---|
| 1 | passed | 19 files, 3 batches (earlier session) |
| 2 | passed | 32 files (earlier session) |
| 3 | passed | 41 files with Part 4 (earlier session) |
| 4 | passed | with Part 3 |
| 5 | passed | earlier session |
| 6 | passed | earlier session |
| 7 | passed | 255 passed |
| 8 | passed | 246 passed |
| 9 | passed | 290 passed |
| 10 | passed after rerun | 855 passed, 8 failed in the full run; the 8 pass by name in `work/part10_11_rerun.log` (7 = test database left at migration 0137 while the code needs 0142; 1 = `test_latency_metrics`, fixed in the code) |
| 11 | passed after rerun | 97 passed, 1 failed (the same latency test); passes by name in the rerun |
| 12 | passed | 211 passed, 2 skipped (PostgreSQL concurrency, run separately: 24 passed) |
| 13 | passed | 143 passed, 1 skipped (staging-only tenant policies). A first run had 119 passed and 25 skipped because the PostgreSQL, S3 and Celery-worker tests were not given their disposable services; they now run (private Redis + worker for `test_e2e_lifecycle`, which proves the real account purge) |
| 14 | passed | 26 passed |
| 15 | passed | 41 passed |

Also executed outside the Part runs: 24 PostgreSQL concurrency tests (credits, invoices, subscriptions; `RAG_DISPOSABLE_PG_URL` on a scratch database) and 38 SQL-tool tenant-bypass tests including the PostgreSQL proofs (`P0_PG_TEST_URL`), both skipped before; the full user lifecycle (register to real Celery purge); Playwright 12/12 in Chrome.

## Found and fixed

- **5.4.8 code block** (HIGH): three bypasses of the whitelist reproduced then fixed: dunder attribute read through `str.format`, unbounded memory through repeat / replace / join (a replace turned 1 MB into 1 GB), unhandled MemoryError / RecursionError / ZeroDivisionError. 30 tests.
- **10.1.9 SSRF**: the escalation webhook posted to any URL with a plain client; it now uses the SSRF-safe client (a loopback server proves it). The 60 modules that call httpx directly were reviewed; a contract test fails on a new unreviewed one.
- **13.4.8 Azure Terraform**: `for_each` over a sensitive map is rejected by Terraform; fixed. AWS, GCP and Azure pass `terraform validate` and `fmt -check`.
- **7.2.13 latency**: `measure_latency` recomputed the quality metrics of every stored result on each run (quadratic, and it spent the 60 s budget loading an embedding model); the latency test failed in the full runs and passed alone. Fixed in the code, not in the test; the new test fails without the fix.
- **13.1.9 bandit**: 12 findings triaged, 5 left (Hugging Face `from_pretrained` without a pinned revision).
- **2.1.13 to 2.1.18** import screen: GitHub issues, Google Drive, Google Docs, Confluence and OneDrive were API-only.
- **13.2.4 / 13.3.7**: Playwright 12/12 in Chrome (the harness had an ambiguous `role=alert` selector, hard-coded ports and a CORS origin tied to port 3001, all fixed); the end-to-end workflow also runs nightly; `actionlint` passes on all 8 workflows.

## Open: needs an owner decision or an account (not code that can be finished here)

- **Refunds and disputes (BILL-016, 12.1.3)**: invoices have no link to the provider charge and `charge.refunded` is ignored. A fix needs a schema change and a policy (are credits taken back?).
- **Coupons (12.1.4)**: `percent_off` is recorded but not applied at checkout (two providers, real money, no sandbox).
- **Root `render.yaml`** still describes the old Streamlit prototype; the real blueprint is `deploy/render/render.api.yaml`. Render reads the root file automatically if a Blueprint is linked, so replacing it is a deployment decision.
- **Row level security (1.3.5, CRITICAL)**: enabled without policies; the strategy decision is D8 in `docs/DECISIONS.md`.
- **Product name (14.4.1) and logo (14.4.2)**, **custom SLA (10.4.12)**.
- **Real provider sandboxes**: Stripe / Paystack (12.x), LLM / embedding providers (4.x), Slack / Teams / Discord (9.4.x), Twilio / STT / TTS (8.2.x), ClamAV (10.1.12), tracing and error tracking (10.3 / 13.5).

## WRITTEN_NOT_EXECUTED (19)

- **1.1.10** Suppression du compte - written; runner tests pass; the cron job is not applied on Render
- **1.3.5** Isolation des données - CI now runs the PostgreSQL integration files; RLS not enabled
- **10.1.14** Encryption at rest - documented; provider settings not verified
- **13.1.6** Coverage > 90% - target not reached
- **13.2.7** LLM tests - written; not run (no paid key)
- **13.2.8** RAG tests - written; not run (no paid key)
- **13.2.10** Database tests - CI now runs the PostgreSQL integration files; RLS not enabled
- **13.4.3** Render - written, not executed on a real platform
- **13.4.4** Railway - written, not executed on a real platform
- **13.4.5** Fly.io - written, not executed on a real platform
- **13.4.9** DigitalOcean - written, not executed on a real platform
- **14.1.11** Troubleshooting - written
- **14.2.7** Demo video - built
- **14.3.2** Demo - written; typecheck and lint pass; not viewed in a browser
- **14.3.4** Architecture - written; typecheck and lint pass; not viewed in a browser
- **14.3.8** Documentation - written; typecheck and lint pass; not viewed in a browser
- **14.4.2** Logo - owner decision pending
- **14.4.4** Charte graphique - written
- **15.2.7** Benchmark → amélioration - mechanism exists; not run on real data

## VALIDATED_NOT_DEPLOYED (13)

- **10.4.7** Dedicated tenant - validated with the official tool; not applied to a real account or cluster
- **10.4.8** Dedicated database - validated with the official tool; not applied to a real account or cluster
- **10.4.9** Private deployment - validated with the official tool; not applied to a real account or cluster
- **10.4.10** On-premise deployment - validated with the official tool; not applied to a real account or cluster
- **10.4.11** VPC deployment - validated with the official tool; not applied to a real account or cluster
- **13.2.11** Deployment tests - validated with actionlint; workflows not run on GitHub
- **13.3.8** Deploy - validated with actionlint; workflows not run on GitHub
- **13.4.6** AWS - validated with the official tool; not applied to a real account or cluster
- **13.4.7** GCP - validated with the official tool; not applied to a real account or cluster
- **13.4.8** Azure - validated with the official tool; not applied to a real account or cluster
- **13.4.10** Kubernetes - validated with the official tool; not applied to a real account or cluster
- **13.4.11** Helm - validated with the official tool; not applied to a real account or cluster
- **13.4.12** Terraform - validated with the official tool; not applied to a real account or cluster

## BLOCKED_EXTERNAL (26)

- **1.4.3** SSL automatique (Let's Encrypt) - real issuance needs a public DNS name and reachable host; Render/Vercel terminate TLS themselves so this path may be unused in production
- **4.1.1** Anthropic Claude - no real Anthropic call in the audit
- **4.1.2** OpenAI GPT - no real call
- **4.1.3** Google Gemini - no real call
- **4.1.4** Mistral - no real call
- **4.1.5** Ollama (local) - no local Ollama server exercised
- **4.2.1** OpenAI embeddings - no real call
- **4.2.2** Voyage AI - no real call
- **4.2.3** Cohere - no real call
- **5.2.2** Web Search - no real search call
- **5.2.3** GitHub (issues, repos) - no real GitHub call
- **5.2.7** Calendar (Google, Outlook) - no real calendar call
- **5.2.8** Email (Gmail, Outlook, SMTP) - no real mailbox call
- **5.4.10** Bloc Email - no real send
- **5.4.11** Bloc Calendar - no real calendar call
- **8.2.1** Speech-to-text (STT) - no real STT call
- **8.2.2** Text-to-speech (TTS) - no real TTS call
- **9.4.1** Slack - no real Slack workspace exercised
- **9.4.2** Microsoft Teams - no real Teams tenant exercised
- **9.4.3** Discord - no real Discord server exercised
- **10.1.15** Encryption in transit - not verified against the live deployment
- **10.3.6** LLM traces - Datadog not configured
- **10.3.9** Error tracking - Sentry DSN not verified in production
- **11.3.4** Uptime monitoring - no uptime monitor configured to the audit's knowledge
- **13.5.5** LLM traces - Datadog not configured
- **13.5.8** Error tracking - Sentry DSN unverified

## AMBIGUOUS_REQUIREMENT (2)

- **10.4.12** Custom SLA - no technical acceptance criterion
- **14.4.1** Nom produit - no decided brand name found

## IMPLEMENTED_UNVERIFIED (39)

- **1.4.1** Custom domains (app.client.com) [MEDIUM] - real host routing (Vercel/Render custom domain) not exercised
- **1.4.5** Custom email domain [MEDIUM] - real Resend domain verification not exercised
- **1.4.9** Email sender personnalisable [LOW] - real sending not exercised
- **2.2.13** Détection de documents modifiés [MEDIUM] - periodic run needs Celery beat (audit R-02); no UI
- **2.2.14** Synchronisation automatique [MEDIUM] - depends on Celery beat; connectors external
- **2.2.15** Auto-reindexation programmée [MEDIUM] - needs Celery beat; no UI
- **3.4.2** Vector Search [MEDIUM] - which branch production takes is unproven
- **3.4.4** Cross-encoder reranking [MEDIUM] - real model load/latency/memory not measured
- **3.4.7** HyDE [LOW] - quality benefit never measured
- **3.4.8** Multi-query retrieval [LOW] - quality benefit never measured
- **4.1.6** OpenAI-compatible APIs [MEDIUM] - guard application not confirmed in this pass
- **5.3.10** Déploiement [LOW] - meaning of 'deploy to production' not precisely defined in the spec
- **5.4.3** Bloc LLM [LOW] - LLM real call not exercised
- **6.2.5** Unsupported claim detection [MEDIUM] - detection accuracy never measured on real data
- **6.2.6** Claim verification [MEDIUM] - accuracy not measured
- **6.2.7** Contradiction detection [LOW] - accuracy not measured
- **6.2.8** Source consistency check [LOW] - accuracy not measured
- **6.2.9** Hallucination detector [MEDIUM] - accuracy not measured
- **6.2.10** Groundedness score [LOW] - score meaning not validated
- **6.2.11** Faithfulness score [LOW] - score meaning not validated
- **7.2.8** Faithfulness [MEDIUM] - score validity not measured against human labels; no run on a real dataset has produced a baseline (audit R-06)
- **7.2.9** Answer relevance [MEDIUM] - no run on a real dataset has produced a baseline (audit R-06)
- **7.2.10** Context relevance [LOW] - no run on a real dataset has produced a baseline (audit R-06)
- **7.2.11** Citation correctness [LOW] - no run on a real dataset has produced a baseline (audit R-06)
- **7.2.12** Hallucination rate [MEDIUM] - no run on a real dataset has produced a baseline (audit R-06)
- **7.3.1** Automatic evaluation [MEDIUM] - jobs run in Celery (no production worker, audit R-02); never run on real data
- **8.2.3** Streaming voice [LOW] - real-time streaming playback not exercised
- **8.2.5** Voice activity detection [LOW] - only on the demo page; real VAD accuracy not tested
- **12.1.2** Subscriptions [HIGH] - never run against a real provider sandbox; live tests are skipped (audit R-05); recurring renewal events not observed
- **12.1.6** Upgrade [MEDIUM] - never run against a real provider sandbox; live tests are skipped (audit R-05); proration not verified
- **12.1.7** Downgrade [MEDIUM] - never run against a real provider sandbox; live tests are skipped (audit R-05); effect on existing data over new limits not verified
- **12.1.8** Cancellation [MEDIUM] - never run against a real provider sandbox; live tests are skipped (audit R-05)
- **12.1.10** Credits [HIGH] - Paystack credit purchase not supported; currency inconsistency (BILL-018); never run against a real provider sandbox; live tests are skipped
- **12.2.1** Free [MEDIUM] - production plan rows and limits (3 documents, 10 questions/day) not verified; plan data is not in code
- **12.2.2** Starter [LOW] - production values unverified
- **12.2.3** Pro [LOW] - production values unverified
- **12.2.4** Business [MEDIUM] - a Business plan may not exist
- **12.2.5** Enterprise [LOW] - on-premise not delivered as a product
- **12.3.1** AI credits [HIGH] - never run against a real provider sandbox; live tests are skipped (audit R-05)
