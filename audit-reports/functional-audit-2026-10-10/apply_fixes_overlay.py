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
