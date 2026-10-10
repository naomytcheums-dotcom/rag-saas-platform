# 09 - Fixes applied on the fix branch (93 features touched)

`01-feature-verification.csv` is untouched (state of `main` when audited). `01b-feature-verification-after-fixes.csv` adds `fix_status` and `fix_evidence`.

| Feature | Fix status | Evidence |
|---|---|---|
| 1.1.4 | tests pass | frontend/app/verify-email (4 vitest cases) |
| 1.1.5 | tests pass (UI); real provider round-trip not run | frontend/components/auth/OAuthButtons.tsx on login and register, opt-in NEXT_PUBLIC_OAUTH_PROVIDERS (3 vitest cases) |
| 1.1.6 | tests pass (UI); real provider round-trip not run | frontend/components/auth/OAuthButtons.tsx on login and register, opt-in NEXT_PUBLIC_OAUTH_PROVIDERS (3 vitest cases) |
| 1.1.13 | tests pass | users.job_title + migration 0142 + profile field (tests/test_p2_insights.py::test_profile_stores_a_job_title) |
| 1.3.2 | tests pass | frontend/app/dashboard/teams (4 vitest cases) |
| 1.3.3 | tests pass | frontend/app/dashboard/teams (4 vitest cases) |
| 2.2.1 | tests pass | documents page multi-file, drop zone, status polling (3 vitest cases) |
| 2.2.2 | tests pass | documents page multi-file, drop zone, status polling (3 vitest cases) |
| 2.2.3 | tests pass | documents page multi-file, drop zone, status polling (3 vitest cases) |
| 2.2.4 | tests pass | frontend/components/DocumentDetails.tsx (7 vitest cases) |
| 2.2.6 | tests pass | frontend/components/DocumentDetails.tsx (7 vitest cases) |
| 2.2.7 | tests pass | frontend/components/DocumentDetails.tsx (7 vitest cases) |
| 2.2.8 | tests pass | frontend/components/DocumentDetails.tsx (7 vitest cases) |
| 2.2.9 | tests pass | frontend/components/DocumentDetails.tsx (7 vitest cases) |
| 2.2.10 | tests pass | frontend/components/DocumentDetails.tsx (7 vitest cases) |
| 2.2.12 | tests pass | frontend/components/DocumentDetails.tsx (7 vitest cases) |
| 3.4.5 | tests pass | api/services/query_rewriting.py expand_with_synonyms + org settings (tests/test_p2_query_synonyms.py) |
| 5.1.5 | tests pass | api/services/tool_budget.py cap_tool_output wired in the orchestrator (tests/test_tool_budget.py) |
| 5.1.7 | tests pass | api/services/fallback.py run_tool_fallbacks wired in the orchestrator (tests/test_fallback.py) |
| 7.1.7 | tests pass | evaluation split column, assign-split route, job split filter, migration 0137 (tests/test_p2_eval_split_held_out.py) |
| 8.1.8 | tests pass (components); not run in a browser against a live LLM | chat page mounts RetryButton, ShareConversation, ConversationTools (export, visibility), SuggestedQuestions, FollowUpQuestions; persisted ids after streaming |
| 8.1.14 | tests pass (components); not run in a browser against a live LLM | chat page mounts RetryButton, ShareConversation, ConversationTools (export, visibility), SuggestedQuestions, FollowUpQuestions; persisted ids after streaming |
| 8.1.15 | tests pass (components); not run in a browser against a live LLM | chat page mounts RetryButton, ShareConversation, ConversationTools (export, visibility), SuggestedQuestions, FollowUpQuestions; persisted ids after streaming |
| 8.1.16 | tests pass (components); not run in a browser against a live LLM | chat page mounts RetryButton, ShareConversation, ConversationTools (export, visibility), SuggestedQuestions, FollowUpQuestions; persisted ids after streaming |
| 8.1.17 | tests pass (components); not run in a browser against a live LLM | chat page mounts RetryButton, ShareConversation, ConversationTools (export, visibility), SuggestedQuestions, FollowUpQuestions; persisted ids after streaming |
| 8.1.18 | tests pass (components); not run in a browser against a live LLM | chat page mounts RetryButton, ShareConversation, ConversationTools (export, visibility), SuggestedQuestions, FollowUpQuestions; persisted ids after streaming |
| 8.2.7 | tests pass (page tests); real Twilio / voice providers not run | frontend/app/dashboard/voice-settings, VoiceMessageList in chat, AudioPermission around voice input |
| 8.2.8 | tests pass (page tests); real Twilio / voice providers not run | frontend/app/dashboard/voice-settings, VoiceMessageList in chat, AudioPermission around voice input |
| 8.2.9 | tests pass (page tests); real Twilio / voice providers not run | frontend/app/dashboard/voice-settings, VoiceMessageList in chat, AudioPermission around voice input |
| 8.2.11 | tests pass (page tests); real Twilio / voice providers not run | frontend/app/dashboard/voice-settings, VoiceMessageList in chat, AudioPermission around voice input |
| 8.2.13 | tests pass (page tests); real Twilio / voice providers not run | frontend/app/dashboard/voice-settings, VoiceMessageList in chat, AudioPermission around voice input |
| 10.2.3 | tests pass | api/services/output_guard.py redact_output / validate_output (tests/test_p2_output_guard.py), org setting output_guard_enabled (default off) |
| 10.2.5 | tests pass | api/services/output_guard.py redact_output / validate_output (tests/test_p2_output_guard.py), org setting output_guard_enabled (default off) |
| 10.2.6 | tests pass | api/services/output_guard.py redact_output / validate_output (tests/test_p2_output_guard.py), org setting output_guard_enabled (default off) |
| 10.2.7 | tests pass | api/services/toxicity_filter.py (tests/test_p2_toxicity_filter.py), org setting toxicity_filter_enabled (default off) |
| 10.2.8 | tests pass | detect_unsafe_tool_call wired in both orchestrator tool paths (tests/test_p2_output_guard.py) |
| 10.2.10 | tests pass | api/services/output_guard.py redact_output / validate_output (tests/test_p2_output_guard.py), org setting output_guard_enabled (default off) |
| 10.4.3 | tests pass | api/routers/scim.py, scim_tokens, migration 0141 (tests/test_p2_scim.py) |
| 10.4.5 | tests pass | conversation_retention_days + api/tasks/retention.py + beat entry (tests/test_p2_retention.py); the daily task needs a running Celery beat |
| 10.4.6 | tests pass | conversation_retention_days + api/tasks/retention.py + beat entry (tests/test_p2_retention.py); the daily task needs a running Celery beat |
| 10.4.7 | written, not executed on a real platform | deploy/dedicated-tenant (compose + provision.sh), deploy/kubernetes, deploy/helm, docker-compose.selfhosted.yml |
| 10.4.8 | written, not executed on a real platform | deploy/dedicated-tenant (compose + provision.sh), deploy/kubernetes, deploy/helm, docker-compose.selfhosted.yml |
| 10.4.9 | written, not executed on a real platform | deploy/dedicated-tenant (compose + provision.sh), deploy/kubernetes, deploy/helm, docker-compose.selfhosted.yml |
| 10.4.10 | written, not executed on a real platform | deploy/dedicated-tenant (compose + provision.sh), deploy/kubernetes, deploy/helm, docker-compose.selfhosted.yml |
| 10.4.11 | written, not executed on a real platform | deploy/dedicated-tenant (compose + provision.sh), deploy/kubernetes, deploy/helm, docker-compose.selfhosted.yml |
| 11.2.5 | tests pass | api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py) |
| 11.2.7 | tests pass | api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py) |
| 11.2.8 | tests pass | api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py) |
| 11.2.9 | tests pass | api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py) |
| 11.2.10 | tests pass | api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py) |
| 11.2.12 | tests pass (credits only; BYOK organizations show 0) | insights cost-per-user / cost-per-answer from credit transactions |
| 11.2.13 | tests pass (credits only; BYOK organizations show 0) | insights cost-per-user / cost-per-answer from credit transactions |
| 11.2.14 | tests pass | api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py) |
| 11.2.15 | tests pass | api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py) |
| 11.2.16 | tests pass | api/services/insights.py + routers/insights.py + dashboard/insights page (tests/test_p2_insights.py) |
| 12.1.4 | tests pass (bonus credits); percent_off is recorded, not applied at checkout | api/routers/coupons.py, migration 0140 (tests/test_p2_coupons.py) |
| 12.3.6 | tests pass | api/services/voice_usage.py, limit on outbound calls and voice-agent turns (tests/test_p2_voice_minutes.py) |
| 13.1.4 | configured, report-only | [tool.mypy] in pyproject.toml and a non-blocking mypy workflow; the number of type errors is not yet measured |
| 13.4.3 | written, not executed on a real platform | deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean} |
| 13.4.4 | written, not executed on a real platform | deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean} |
| 13.4.5 | written, not executed on a real platform | deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean} |
| 13.4.6 | written, not executed on a real platform | deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean} |
| 13.4.7 | written, not executed on a real platform | deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean} |
| 13.4.8 | written, not executed on a real platform | deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean} |
| 13.4.9 | written, not executed on a real platform | deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean} |
| 13.4.10 | written, not executed on a real platform | deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean} |
| 13.4.11 | written, not executed on a real platform | deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean} |
| 13.4.12 | written, not executed on a real platform | deploy/render, railway, fly, kubernetes, helm, terraform/{aws,gcp,azure,digitalocean} |
| 14.1.11 | written | docs/guides/TROUBLESHOOTING.md |
| 14.2.1 | built and viewed | deliverables/*.pdf via scripts/build_deliverable_pdfs.py (tests/test_build_deliverable_pdfs.py for the converter) |
| 14.2.2 | built and viewed | deliverables/*.pdf via scripts/build_deliverable_pdfs.py (tests/test_build_deliverable_pdfs.py for the converter) |
| 14.2.3 | built and viewed | deliverables/*.pdf via scripts/build_deliverable_pdfs.py (tests/test_build_deliverable_pdfs.py for the converter) |
| 14.2.4 | built and viewed | deliverables/*.pdf via scripts/build_deliverable_pdfs.py (tests/test_build_deliverable_pdfs.py for the converter) |
| 14.2.5 | built and viewed | deliverables/*.pdf via scripts/build_deliverable_pdfs.py (tests/test_build_deliverable_pdfs.py for the converter) |
| 14.2.6 | built and viewed | deliverables/*.pdf via scripts/build_deliverable_pdfs.py (tests/test_build_deliverable_pdfs.py for the converter) |
| 14.2.7 | built | deliverables/product-tour.mp4 (silent screenshot tour on an isolated database) |
| 14.3.3 | assessment corrected | LandingSections.tsx already contains Features, Pricing, Security and FAQ sections (missed by the first pass) |
| 14.3.6 | assessment corrected | LandingSections.tsx already contains Features, Pricing, Security and FAQ sections (missed by the first pass) |
| 14.3.7 | assessment corrected | LandingSections.tsx already contains Features, Pricing, Security and FAQ sections (missed by the first pass) |
| 14.3.9 | assessment corrected | LandingSections.tsx already contains Features, Pricing, Security and FAQ sections (missed by the first pass) |
| 14.4.4 | written | docs/commercial/BRAND_GUIDE.md (product name and logo still undecided: 14.4.1 / 14.4.2 remain open) |
| 15.1.1 | tests pass | api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases) |
| 15.1.2 | tests pass | api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases) |
| 15.1.3 | tests pass | api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases) |
| 15.1.4 | tests pass | api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases) |
| 15.1.5 | tests pass | api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases) |
| 15.1.6 | tests pass | api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases) |
| 15.1.7 | tests pass | api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases) |
| 15.1.8 | tests pass | api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases) |
| 15.1.9 | tests pass | api/routers/escalations.py, escalation_notes + sla_due_at (migration 0138), dashboard/escalations page (tests/test_p2_escalation_tickets_api.py, 5 vitest cases) |
| 15.2.4 | tests pass | message_feedback.correction (migration 0139), feedback/analysis, feedback/to-evaluation (tests/test_p2_insights.py) |
| 15.2.5 | tests pass | message_feedback.correction (migration 0139), feedback/analysis, feedback/to-evaluation (tests/test_p2_insights.py) |
| 15.2.6 | tests pass | message_feedback.correction (migration 0139), feedback/analysis, feedback/to-evaluation (tests/test_p2_insights.py) |

Migrations to apply (by the owner, after a backup): 0137 evaluation split, 0138 escalation SLA and notes, 0139 feedback correction, 0140 coupons, 0141 SCIM tokens, 0142 job title.
