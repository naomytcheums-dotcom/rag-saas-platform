"""Overlay: which audited gaps were addressed on the fix branch (PR #24), without touching 01-feature-verification.csv.

Writes 01b-feature-verification-after-fixes.csv = every row of 01 plus `fix_status` / `fix_evidence`, and 09-fixes-applied.md.
A fix is listed here only when code and a test exist on the branch; `fix_status` says whether it is proven by tests or only written (deployment assets)."""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
T = "tests pass"
W = "written, not executed on a real platform"
FIXES: dict[str, tuple[str, str]] = {}


def add(ids, status, evidence):
    for i in ids:
        FIXES[i] = (status, evidence)


add(["1.1.4"], T, "frontend/app/verify-email (4 vitest cases)")
add(["1.1.5", "1.1.6"], T + " (UI); real provider round-trip not run", "frontend/components/auth/OAuthButtons.tsx on login and register, opt-in NEXT_PUBLIC_OAUTH_PROVIDERS (3 vitest cases)")
add(["1.1.13"], T, "users.job_title + migration 0142 + profile field (tests/test_p2_insights.py::test_profile_stores_a_job_title)")
add(["1.3.2", "1.3.3"], T, "frontend/app/dashboard/teams (4 vitest cases)")
add(["2.2.1", "2.2.2", "2.2.3"], T, "documents page multi-file, drop zone, status polling (3 vitest cases)")
add(["2.2.4", "2.2.6", "2.2.7", "2.2.8", "2.2.9", "2.2.10", "2.2.12"], T, "frontend/components/DocumentDetails.tsx (7 vitest cases)")
add(["3.4.5"], T, "api/services/query_rewriting.py expand_with_synonyms + org settings (tests/test_p2_query_synonyms.py)")
add(["5.1.5"], T, "api/services/tool_budget.py cap_tool_output wired in the orchestrator (tests/test_tool_budget.py)")
add(["5.1.7"], T, "api/services/fallback.py run_tool_fallbacks wired in the orchestrator (tests/test_fallback.py)")
add(["7.1.7"], T, "evaluation split column, assign-split route, job split filter, migration 0137 (tests/test_p2_eval_split_held_out.py)")
add(["8.1.8", "8.1.14", "8.1.15", "8.1.16", "8.1.17", "8.1.18"], T + " (components); not run in a browser against a live LLM", "chat page mounts RetryButton, ShareConversation, ConversationTools (export, visibility), SuggestedQuestions, FollowUpQuestions; persisted ids after streaming")
add(["8.2.7", "8.2.8", "8.2.9", "8.2.11", "8.2.13"], T + " (page tests); real Twilio / voice providers not run", "frontend/app/dashboard/voice-settings, VoiceMessageList in chat, AudioPermission around voice input")
add(["10.2.3", "10.2.5", "10.2.6", "10.2.10"], T, "api/services/output_guard.py redact_output / validate_output (tests/test_p2_output_guard.py), org setting output_guard_enabled (default off)")
add(["10.2.7"], T, "api/services/toxicity_filter.py (tests/test_p2_toxicity_filter.py), org setting toxicity_filter_enabled (default off)")
add(["10.2.8"], T, "detect_unsafe_tool_call wired in both orchestrator tool paths (tests/test_p2_output_guard.py)")
add(["10.4.3"], T, "api/routers/scim.py, scim_tokens, migration 0141 (tests/test_p2_scim.py)")
add(["10.4.5", "10.4.6"], T, "conversation_retention_days + api/tasks/retention.py + beat entry (tests/test_p2_retention.py); the daily task needs a running Celery beat")
add(["10.4.7", "10.4.8", "10.4.9", "10.4.10", "10.4.11"], W, "deploy/dedicated-tenant (compose + provision.sh), deploy/kubernetes, deploy/helm, docker-compose.selfhosted.yml")
add(["11.2.5", "11.2.7", "11.2.8", "11.2.9", "11.2.10", "11.2.14", "11.2.15", "11.2.16"], T, "api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py)")
add(["11.2.12", "11.2.13"], T + " (credits only; BYOK organizations show 0)", "insights cost-per-user / cost-per-answer from credit transactions")
add(["12.1.4"], T + " (bonus credits); percent_off is recorded, not applied at checkout", "api/routers/coupons.py, migration 0140 (tests/test_p2_coupons.py)")
add(["12.3.6"], T, "api/services/voice_usage.py, limit on outbound calls and voice-agent turns (tests/test_p2_voice_minutes.py)")
add(["13.1.4"], "configured, report-only", "[tool.mypy] in pyproject.toml and a non-blocking mypy workflow; the number of type errors is not yet measured")
add(["13.4.3", "13.4.4", "13.4.5", "13.4.6", "13.4.7", "13.4.8", "13.4.9", "13.4.10", "13.4.11", "13.4.12"], W, "deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean}")
add(["14.1.11"], "written", "docs/guides/TROUBLESHOOTING.md")
add(["14.2.1", "14.2.2", "14.2.3", "14.2.4", "14.2.5", "14.2.6"], "built and viewed", "deliverables/*.pdf via scripts/build_deliverable_pdfs.py (tests/test_build_deliverable_pdfs.py for the converter)")
add(["14.2.7"], "built", "deliverables/product-tour.mp4 (silent screenshot tour on an isolated database)")
add(["14.3.3", "14.3.6", "14.3.7", "14.3.9"], "assessment corrected", "LandingSections.tsx already contains Features, Pricing, Security and FAQ sections (missed by the first pass)")
add(["14.4.4"], "written", "docs/commercial/BRAND_GUIDE.md (product name and logo still undecided: 14.4.1 / 14.4.2 remain open)")
add(["15.1.1", "15.1.2", "15.1.3", "15.1.4", "15.1.5", "15.1.6", "15.1.7", "15.1.8", "15.1.9"], T, "api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases)")
add(["15.2.4", "15.2.5", "15.2.6"], T, "message_feedback.correction (migration 0139), feedback/analysis, feedback/to-evaluation (tests/test_p2_insights.py)")

add(["1.2.6"], T, "tests/test_p2_viewer_route_matrix.py: 233 organization write operations probed as a viewer, only 3 reachable (search, template preview, plugin review), all allow-listed with a reason")
add(["1.3.6", "12.3.2", "12.3.3"], T, "api/security/document_capacity.py: plan document limit now also on the batch upload and the 9 importers, storage quota enforced on upload and batch (tests/test_p2_document_capacity.py)")
add(["1.3.7"], T, "per-user rate limit on /chat/stream (CHAT_USER_RATE_LIMIT_*; fails open without Redis) (tests/test_p2_chat_user_rate_limit.py)")
add(["6.1.8"], T, "GET /citations/{id}/preview wires api/services/citation_preview.py (tests/test_p2_citation_preview_route.py)")
add(["11.3.7", "11.3.8"], T + " (configuration probes, not live calls)", "admin system health now reports pgvector extension status and which LLM providers have a platform key (tests/test_p2_health_probes.py)")
add(["5.4.12"], "assessment corrected", "the database workflow block reuses the SQL tool validator and tenant filter, covered by tests/test_workflow_block_database.py and the P0 SQL bypass test")

add(["1.1.11"], T, "authenticated download of the personal data export from the profile page (frontend/lib/download.ts, 3 vitest cases)")
add(["15.2.1", "15.2.2", "15.2.3"], T + " (components); not run in a browser against a live LLM", "frontend/components/FeedbackButtons.tsx: thumbs, reason categories, free comment and correction (vitest) on top of migration 0139")
add(["2.1.11"], T + " (UI); real remote sitemaps not fetched", "frontend/components/ImportSources.tsx: sitemap, URL, GitHub, Notion and other importers from the documents page (5 vitest cases)")
add(["7.1.8"], T, "eval_datasets/verticals/{fastapi,legal,hr,finance}.csv, 15 questions each, imported through the real endpoint (tests/test_eval_vertical_datasets.py, 12 cases)")
add(["13.2.4", "13.3.7"], "executed locally: 10/10 passed; not wired into CI", "e2e/ Playwright package (login, register, dashboard pages, documents, escalations) run against the real API and Next.js on a disposable database")
add(["14.3.2", "14.3.4", "14.3.8"], "written; typecheck and lint pass; not viewed in a browser", "landing page: product-tour video, four-step architecture section, documentation PDF links (frontend/components/figma/LandingSections.tsx)")
add(["10.1.3"], T + " (UI); real provider round-trip not run", "OAuth buttons on the login and register screens (same component as 1.1.5, 1.1.6)")
add(["10.1.4"], T, "tests/test_p2_viewer_route_matrix.py: route x role matrix checked against the real routers")
add(["13.3.2"], "configured, report-only", "pyproject.toml [tool.mypy] and .github/workflows/mypy.yml (non-blocking: the existing code base is not yet type clean)")
add(["13.1.3"], "decision recorded", "docs/DECISIONS.md: ruff format is the formatter (Black-compatible output); Black is not added as a second tool")
add(["14.1.2"], "documentation corrected", "agents.md now lists the real Eval Lab and MCP routes (verified against the OpenAPI document); docs/architecture/LEGACY.md not re-audited")

add(["1.1.10"], "written; runner tests pass; the cron job is not applied on Render", "scripts/run_maintenance_tasks.py runs the account purge and the other daily clean-ups without a worker; cron entry in deploy/render/render.api.yaml (tests/test_run_maintenance_tasks.py)")
add(["1.2.7"], T, "tests/test_route_auth_classification.py: the 101 operations open without a bearer token are on a reviewed list with reasons; a new open route fails the test")
add(["1.2.8"], "assessment corrected; decision recorded", "grants are accepted only for resource types that enforce them (workspaces); other types are rejected with 400; scope and extension path in docs/DECISIONS.md D11")
add(["1.3.5", "13.2.10"], "CI now runs the PostgreSQL integration files; RLS not enabled", "backend-tests starts a pgvector PostgreSQL with all migrations; 61 PostgreSQL integration tests pass locally; RLS rollout decision in D8")
add(["1.4.6", "1.4.8"], T + " (components)", "organization brand name in the chat header and tab title, accent colour and font applied across the interface (frontend/components/BrandingApplier.test.tsx)")
add(["3.1.5"], "assessment corrected", "describe_embedded_image_if_enabled already calls a vision model per embedded image (off by default, MULTIMODAL_DESCRIBE_DOCUMENT_IMAGES); tested with a fake provider (tests/backend/media/test_media_finalization.py); no real vision call run")
add(["5.1.13"], T + " (opt-in TASK_PLAN_EXECUTE_STEPS)", "the plan can be executed step by step and its results reach the final answer (tests/test_agent_orchestrator.py); default stays advisory")
add(["6.2.12", "11.2.6"], T + " (page tests)", "frontend/app/dashboard/quality-scores: averages, trend, per-answer scores, CSV export")
add(["10.1.14"], "documented; provider settings not verified", "docs/DECISIONS.md D12: what the application encrypts and what depends on Supabase")
add(["10.4.2"], "decision recorded; not built", "docs/DECISIONS.md D9: python3-saml behind a flag after a security review")
add(["10.4.4"], "decision recorded", "docs/DECISIONS.md D10: built-in roles plus custom roles, SCIM-provisioned")
add(["12.1.5"], T + " (opt-in STRIPE_CHECKOUT_TRIAL_DAYS); no sandbox run", "Stripe trial_period_days on the subscription checkout (tests/test_p1_bill003_005_006_stripe_chain.py)")
add(["12.1.9"], "decision recorded", "docs/DECISIONS.md D13: prepaid credits")
add(["12.1.1"], "decision recorded; sandbox run still to do", "docs/DECISIONS.md D14: Stripe and Paystack, no Flutterwave")
add(["13.1.1"], "measured; ratchet test", "scripts/type_hint_coverage.py: 69.1 % of api/ functions fully annotated; tests/test_type_hint_coverage.py stops it falling")
add(["13.2.7", "13.2.8"], "written; not run (no paid key)", "tests/llm_optin/test_real_llm.py and .github/workflows/llm-tests.yml, skipped unless RUN_REAL_LLM_TESTS=1")
add(["13.2.11", "13.3.8"], "written; smoke tests pass; workflows not run", "scripts/post_deploy_smoke.py (tests/test_post_deploy_smoke.py), .github/workflows/post-deploy-smoke.yml and migrate.yml (manual, rehearsal by default)")
add(["13.5.12"], T, "GET /responses/{id}/trace joins retrieval, generation, checks, agent steps and citations (tests/test_p2_request_trace.py)")
add(["14.1.2"], "documentation corrected", "agents.md routes verified against OpenAPI; docs/architecture/OVERVIEW.md now has component, chat and ingestion diagrams; the multi-tenant line no longer claims RLS policies")

add(["13.1.6"], "target not reached", "measured about 77 % on the CircleCI subset; the 90 % target needs many more tests, not a configuration change")
add(["14.4.2"], "owner decision pending", "docs/DECISIONS.md D3 and docs/commercial/BRAND_GUIDE.md: no logo is invented; the guide lists what to change once one is chosen")
add(["15.2.7"], "mechanism exists; not run on real data", "feedback can be turned into evaluation questions (POST /organizations/{id}/feedback/to-evaluation); no benchmark on real user data has been run")

# 2026-10-11 session: only what was really executed.
V = "validated with the official tool; not applied to a real account or cluster"
add(["13.4.6", "13.4.7", "13.4.8", "13.4.12"], V, "terraform validate and fmt -check pass for deploy/terraform/{aws,gcp,azure} (hashicorp/terraform 1.9, init -backend=false); the Azure module had a real error (for_each over a sensitive map) that this run found and fixed")
add(["13.4.10", "13.4.11"], V, "helm lint (0 failed), helm template parsed by kubeconform strict (4/4 valid), deploy/kubernetes/rag-saas.yaml kubeconform strict (7/7 valid)")
add(["10.4.7", "10.4.8", "10.4.9", "10.4.10", "10.4.11"], V, "deploy/dedicated-tenant/provision.sh passes shellcheck; the helm chart and the Kubernetes manifest are validated as above; docker compose config -q passes for docker-compose.tenant.yml and docker-compose.selfhosted.yml (also with the proxy profile) once the required variables are given dummy values")
add(["5.4.8"], T + " (security review done)", "the code block is an ast whitelist evaluator, not exec(); the review reproduced 3 bypasses (dunder access through str.format, unbounded memory through repeat/replace/join, unhandled MemoryError/RecursionError) and fixed them (tests/test_workflow_block_code_hardening.py, 30 cases); a process or container sandbox is not needed for this design")
add(["10.1.9"], T, "tests/test_outbound_http_inventory.py: the 60 modules that call httpx directly were reviewed (hosts are constants or platform settings); the escalation webhook now goes through ssrf_safe_client (a loopback server proves it is not reached); a new unreviewed direct call fails the test")
add(["13.1.9"], "triaged; 12 findings -> 5 left", "bandit -ll: MD5 marked usedforsecurity=False, 4 false positives annotated with the reason, migrations excluded; 5 left = Hugging Face from_pretrained without a pinned revision (accepted until the model list is frozen)")
add(["2.1.12", "2.1.13", "2.1.14", "2.1.15", "2.1.16", "2.1.17", "2.1.18"], T + " (UI); credentials are now per organization (D17 fixed, 38 + 17 tests); real provider calls not run", "frontend/components/ImportSources.tsx now offers GitHub repository and issues, Google Drive and Docs, Notion, Confluence and OneDrive (10 vitest cases, tsc and eslint clean)")
add(["1.3.8"], "assessment corrected", "the billing page already has a Usage tab (frontend/app/dashboard/billing/page.tsx, UsageTab) fed by GET /organizations/{id}/billing/usage and /usage/forecast, for members with billing:manage; the route is covered by tests/test_billing.py (usage case passes); the tab itself has no component test")
add(["8.2.6"], "assessment corrected", "VoiceSettings.tsx is mounted by frontend/app/dashboard/voice-settings/page.tsx (2 vitest cases pass, 2026-10-11); the first pass looked for an importer and missed the page")
add(["2.2.16"], "assessment corrected; production worker still needed", "the documents page already offers multi-file upload with live status (frontend/app/dashboard/documents, 3 vitest cases, see 2.2.1 to 2.2.3); what remains is a running Celery worker in production (deploy/render/render.api.yaml defines it, not applied)")
add(["3.1.6"], T + " (Tesseract 5.4 with eng and fra, 17 tests run, none skipped)", "tests/test_ocr.py run with the Tesseract and Poppler binaries and the French language data; the scanned-PDF path through the documents pipeline needs the S3 stack and was not rerun here")
add(["10.1.12"], T + " (real clamd 1.5.4 in Docker); no scanner is deployed in production (CLAMAV_ENABLED defaults to off)", "tests/test_clamav_real_daemon.py, 8 cases: EICAR refused, clean and 3 MB files accepted, fail closed when the scan is required and the daemon is down, infected refused even when optional, and the document upload endpoint answers 400 for EICAR and 201 for a clean file")
add(["10.3.5", "13.5.4"], T + " (real Jaeger); no collector is deployed in production (OTEL_ENABLED defaults to off)", "tests/test_tracing_real_collector.py: setup_tracing exports the spans of a real request over OTLP/HTTP and the trace is read back from a running Jaeger 1.76; found on the way that the test environment inherited the production Tempo credentials, now blanked in scripts/run_tests_local.sh")
add(["13.1.4", "13.3.2"], "measured; report-only", "mypy 2.4.0 on api/: 305 errors in 110 of 707 source files (measured 2026-10-11); the workflow stays non-blocking until that number is brought down")
add(["10.1.8", "10.2.1", "10.2.2"], "measured; flag rather than block", "protectai/deberta-v3-base-prompt-injection-v2 at threshold 0.75 on 92 labelled sentences (43 attacks, 49 legitimate, English and French): recall 0.953, false positive rate 0.122 with 3 of 6 false positives in French; tests/test_prompt_injection_measured.py (opt-in) guards it; docs/DECISIONS.md D15 keeps the detector off by default and says not to block with it yet")
add(["10.4.12"], T + " (software side only)", "acceptance criterion written in tests/test_custom_sla.py: an organization sets escalation_sla_hours per priority (critical, high, medium, low; 1 to 720 hours, strict integers), tickets of that organization carry sla_due_at = creation + that delay, other priorities and other organizations keep ESCALATION_SLA_HOURS, invalid values answer 422 (9 cases); uptime commitments and credits remain a contract matter (docs/commercial)")
add(["14.4.1"], "decision recorded", "owner decision 2026-10-11: the product name is 'RAG SaaS Platform', already shown by the interface (layout title, app_name, brand fallback); docs/DECISIONS.md D3 and docs/commercial/BRAND_GUIDE.md updated; e-mail sender name, widget title and PDFs still to check at publication")
add(["2.2.13", "2.2.15"], T + " (real Celery beat + worker, empty database); no beat/worker deployed in production", "scripts/test_env/celery_beat_probe.py: check_modified_documents_task and check_scheduled_reindexes_task were scheduled by a real beat every 8 s and executed by a real worker 10 times each, 0 failures (17 periodic tasks, 170 executions in total); an empty database proves scheduling, dispatch and no crash, not the processing of real data")
add(["2.2.14"], T + " (scheduling only; real external sources not reached)", "sync_all_sources_periodic_task ran 10 times under a real beat and worker without failure on an empty database; no external connector was exercised")
add(["3.4.2"], T + " (real pgvector 0.8.7 on PostgreSQL, HNSW index)", "tests/test_pgvector_real_search.py (opt-in PGVECTOR_REAL_TEST=1): the native branch _pgvector_rank_chunks applies (does not fall back to numpy), a paraphrased question finds the right passage first among 8, a near-identical passage of another organization is never returned, and the ranking equals an independent cosine computation; which branch the hosting provider's database takes is still to check there (extension and index must exist)")
add(["3.4.4"], "measured; sizing consequence", "docs/PERFORMANCE_REPORT.md: cross-encoder MiniLM-L6 on a 16-thread CPU: load 20.6 s, +561 MB of memory, 152 ms for 10 candidates, 222 ms for 20, 596 ms for 50; to be measured again on the hosting plan")
add(["10.1.8", "10.2.1", "10.2.2"], "measured; second opinion built, to be measured with a real model", "classifier alone on 92 labelled sentences: recall 0.953, false positive rate 0.122 (3 of 6 in French); api/services/prompt_injection_detection.py now re-reads only flagged messages with a language model that can clear but never block on its own (tests/test_prompt_injection_second_opinion.py, 24 cases with a fake model); the combined recall and false positive rate with a real model are not measured yet; agents created by the factory have detection ON by default")
add(["1.3.8"], "assessment corrected", "the billing page already has a Usage tab (frontend/app/dashboard/billing/page.tsx, UsageTab) fed by GET /organizations/{id}/billing/usage and /usage/forecast, for members with billing:manage; the route is covered by tests/test_billing.py (usage case passes); the tab itself has no component test")
add(["13.2.4", "13.3.7"], T + " (12/12 in Chrome, 2026-10-11); nightly workflow not yet observed on GitHub", "e2e/ Playwright: login, wrong password, register then dashboard, landing page (video, architecture, PDFs), 5 dashboard pages, documents drop zone, chat without an agent, escalations filter; run against the isolated API (SQLite) and the Next dev server in the installed Chrome. Two selector/port problems found and fixed in the harness (ambiguous role=alert; ports and the CORS origin now configurable); .github/workflows/e2e.yml also runs nightly")
add(["13.2.11", "13.3.8"], "validated with actionlint; workflows not run on GitHub", "actionlint passes on all 8 workflows; scripts/post_deploy_smoke.py tests pass; migrate.yml is manual with a rehearsal by default")

with open(os.path.join(HERE, "01-feature-verification.csv"), encoding="utf-8-sig", newline="") as fh:
    rows = list(csv.DictReader(fh))
fields = list(rows[0].keys()) + ["fix_status", "fix_evidence"]
with open(os.path.join(HERE, "01b-feature-verification-after-fixes.csv"), "w", encoding="utf-8-sig", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        status, evidence = FIXES.get(row["feature_id"], ("", ""))
        writer.writerow({**row, "fix_status": status, "fix_evidence": evidence})

unknown = sorted(set(FIXES) - {r["feature_id"] for r in rows})
with open(os.path.join(HERE, "09-fixes-applied.md"), "w", encoding="utf-8") as fh:
    fh.write(f"# 09 - Fixes applied on the fix branch ({len(FIXES)} features touched)\n\n")
    fh.write("`01-feature-verification.csv` is untouched (state of `main` when audited). `01b-feature-verification-after-fixes.csv` adds `fix_status` and `fix_evidence`.\n\n")
    fh.write("| Feature | Fix status | Evidence |\n|---|---|---|\n")
    for fid in sorted(FIXES, key=lambda x: tuple(int(p) for p in x.split("."))):
        fh.write(f"| {fid} | {FIXES[fid][0]} | {FIXES[fid][1]} |\n")
    fh.write("\nMigrations to apply (by the owner, after a backup): 0137 evaluation split, 0138 escalation SLA and notes, 0139 feedback correction, 0140 coupons, 0141 SCIM tokens, 0142 job title.\n")
print("features touched:", len(FIXES), "unknown ids:", unknown)
