# 02 - Functional specification by module

This is the functional description of what the product does, organised by family. For every feature one by one (514 rows with evidence and status) see `12_COMPLETE_FEATURE_CATALOG.md`. For the exact routes see `annex/api_routes.csv` (983 operations); for pages `annex/frontend_pages.csv` (64 pages).

Tags: **[V]** verified in code during this mission; **[R]** run/measured in project sessions; **[D]** documented elsewhere in the repo, not re-verified; **[U]** unknown. Four availability levels are kept apart for each family: *specified* (cahier des charges), *implemented* (code exists), *tested* (a green test), *deployed* (observed running in a hosted environment). **Nothing below is claimed "deployed" except what 11_KNOWN_ISSUES says was observed**; the hosted state itself was not accessed (see 10_TESTS_CI_CD_AND_DEPLOYMENT.md).

## Roles and permissions model [V]
* **Platform level:** `UserRole` includes a superadmin (the operator).
* **Organization level (`OrganizationRole`, `api/models/organization.py`):** `owner`, `admin`, `manager`, `member`, `viewer`. A user can belong to several organizations.
* **Custom roles (Casbin policies, `api/services/rbac_custom.py`):** an organization can define roles from a **fixed catalog of 52 permissions** = 13 resources (documents, agents, conversations, api_keys, webhooks, widget, integrations, evaluation, billing, members, settings, security, audit_logs) x 4 actions (read, write, delete, manage; `manage` implies the other three). Fixed in code on purpose: a permission nothing checks would look granted but do nothing (`api/security/permission_catalog.py`).
* **Route protection convention:** dependencies named `require_*` (for example `require_permission("integrations:write")`). `tests/test_route_auth_classification.py` fails if a new route is open without being classified, and `tests/test_p2_viewer_route_matrix.py` checks route x role behaviour [D, run in CI].
* **Per-resource grants** exist only for workspaces (D11); **agent tool permissions** have their own enforcement (`api/services/agent_permissions.py`).

---
## F1 - Accounts, sessions, identity (Part 1.1, 10.x)
**Purpose:** let people sign up and sign in safely. **Users:** everyone.
**Features [V]:** e-mail + password registration with strength, similarity and breached-password checks; e-mail verification (Resend); login with timing-side-channel mitigation; JWT access tokens (15 min) with revocation list and key rotation; refresh token in an httpOnly cookie with CSRF token; TOTP two-factor with recovery codes and lock-out recovery; WebAuthn (passkeys); OAuth sign-in (Google, Microsoft and others via `/auth/oauth/{provider}`); enterprise OIDC SSO (`/auth/sso/*`) and SCIM 2.0 provisioning (`/scim/v2/*`); password reset; account deletion in two stages with reminders and a restore link; GDPR consent tracking and forced re-consent when terms change; persistent account lock-out; new-login notifications; session list/revoke.
**Routes:** 32 `auth`, 15 `account`, 2 `sessions`, 10 `scim`. **Pages:** `/login`, `/register`, `/forgot-password`, `/reset-password`, `/verify-email`, `/2fa-lockout-recovery`, `/restore-account`, `/reactivate-consent`, `/oauth-callback`, `/dashboard/profile`, `/dashboard/security`.
**Tests:** `tests/test_auth_api.py`, `test_auth_security.py`, oauth/2FA/WebAuthn files, 2FA-bypass regression tests [D]. **Limits:** SAML is not built (D1/D9). E-mail delivery depends on Resend (not exercised against the real provider in the audit).

## F2 - Organizations, members, teams, workspaces, quotas (Part 1.2-1.4)
**Purpose:** the tenant model. An **organization** is the customer; **workspaces** subdivide its content; **teams** group members; **invitations** add users; **quotas / user limits** cap documents, size and members per plan.
**Features [V]:** create/update organizations; member management with roles; per-member limits; invitations (`/invitations/accept`); teams; workspaces (with description, migration 0132); organization settings (language, timezone, retrieval and LLM defaults - the `DEFAULT_SETTINGS` dictionary is documented in 04_RAG_PIPELINE); custom domains with DNS verification and automatic TLS certificate issuance/renewal (ACME; `custom_domains`, `ssl_certificates`, `email_domains`); quotas and usage endpoints.
**Routes:** 9 `organizations`, 9 `teams`, 5 `organization-settings`, 4 `workspaces`, 4 `invitations`, 2 `quotas`, 3 `user-limits`, 6 `custom-domains`, 4 `ssl-certificates`, 3 `email-domains`, 4 `usage`, 4 `resource-permissions`. **Pages:** `/dashboard/teams`, `/dashboard/settings/organization`, `/invitations/accept`.
**Limit:** isolation is enforced by application filters (every query scoped by `organization_id`); the database row-level-security barrier is intentionally not active (D2/D8).

## F3 - Knowledge base: documents and ingestion (Part 2, 3.1)
**Purpose:** get content into a searchable form. Detail in `04_RAG_PIPELINE_DEEP_DIVE.md`.
**Formats [V]:** PDF (text + OCR), DOCX, TXT, Markdown, HTML, CSV, JSON, XML, EPUB, images (OCR, vision description, YOLOv8 objects, CLIP), audio and video (transcription, frames), ZIP archives. **Sources:** upload, URL, sitemap, GitHub repository, GitHub issues, Google Drive, Google Docs/Sheets/Slides, Notion, Confluence, OneDrive, and 30+ other CRM/ticketing extractors; external-source sync (`external_sources`, daily task). **Management:** versions, tags, audit log per document, batch jobs, scheduled reindex, duplicate detection by content hash, soft delete and retention, language detection, heading extraction, metadata normalization.
**Routes:** 42 `documents`, 5 `batch-jobs`, 5 `external-sources`, 4 `reindex-schedules`, 1 `documents-sync`, 14 `media`. **Pages:** `/dashboard/documents` (with the import-source screen `ImportSources.tsx`), `/dashboard/media`.
**Limits:** antivirus (ClamAV) is **off by default** (`CLAMAV_ENABLED=False`); OCR language default `fra`; Whisper/Tesseract/poppler/YOLO/CLIP need system or ML dependencies that exist only in the "full" image.

## F4 - Retrieval and answering (Part 3.2-3.4, 4, 6)
**Purpose:** answer a question from the organization's chunks with citations. **Strategies [V]:** `hybrid` (default), `vector_only`, `bm25_only`, `hybrid_reranked`, `semantic`; options HyDE, multi-query, query rewriting/expansion, MMR, context compression, metadata filtering, semantic filtering, duplicate removal, GraphRAG (LightRAG), policy-aware retrieval (OPA), adaptive routing; all the *advanced* options are **off by default per organization** (`DEFAULT_SETTINGS`).
**Answer features [V]:** inline `[n]` citations, structured citations with document, page/section, URL, passage, preview, relevance label, secondary sources; per-response confidence; anti-hallucination metrics (context relevance, citation correctness, claim verification), optional refusal modes (citation-required, context-only, "I don't know" confidence floor); toxicity filter, output guard (credential/PII redaction) - all opt-in per organization.
**Routes:** 8 `citations`, 27 `conversations`, 2 `chat-stream`, 1 `search`, 1 `retrieval-diagnostics`, 1 `request-trace`. **Pages:** `/chat`.

## F5 - Multi-LLM and embeddings (Part 4)
Providers via LiteLLM and direct adapters: Anthropic (default `LLM_DEFAULT_PROVIDER=anthropic`, default model `claude-sonnet-5-5`), OpenAI, Gemini, Mistral, Ollama, watsonx, any OpenAI-compatible server; per-organization provider/model/temperature/top_p/max_tokens; fallback chains; cost-aware model routing; bring-your-own-key. Embeddings: local sentence-transformers (default `all-MiniLM-L6-v2`, 384 dimensions) and API providers (OpenAI, Voyage, Cohere) through a standalone service. **Page:** `/dashboard/settings/llm-config` [V].

## F6 - Agents, tools and workflows (Part 5, 23) - see `05_AGENTS_AND_AUTOMATIONS.md`
Configurable agents (prompt templates with `{{variables}}`, model, tools, knowledge base, guardrails, memory, permissions, API keys); tool library (search KB, web search via Tavily, URL reader, GitHub, SQL, calculator, calendar, e-mail, human escalation, custom tools); orchestrator with function calling, parallel tools, retries, timeouts, budgets, traces; visual **workflows** with 10 block types and triggers (webhook, schedule); **autonomous agents** with goals, plans, multi-step execution and human approval; **Factory** (agent from a plain requirement). **Pages:** `/dashboard/agents`, `/dashboard/agents/new`, `/dashboard/agents/factory`, `/dashboard/autonomous-agents`, `/dashboard/workflows`.

## F7 - Evaluation Lab and quality loop (Part 7, 11, 13.5)
Datasets and question sets (with `expected_documents`, difficulty, category, tuning/held-out `split`), evaluation jobs, per-question results with metrics, comparison between runs and configurations, regression detection and thresholds, benchmark versions, manual evaluations (human scoring), four vertical datasets (FastAPI, legal, HR, finance), deployment evaluations (evaluate before deploy), A/B tests with significance and auto-decision, quality alerts (Guardian) and a quality dashboard, the Evolution engine and RAG genome/experiments. **Pages:** `/dashboard/eval`, `/dashboard/eval/[datasetId]`, `.../jobs/[jobId]`, `/dashboard/eval/runs/[runId]/comparison`, `/dashboard/eval/evolution`, `/dashboard/quality`, `/dashboard/quality-scores`, `/dashboard/ab-tests`, `/dashboard/insights`. **Routes:** 12 `evaluation-datasets`, 9 `question-sets`, 8 `evaluation-jobs`, 17 `comparison-jobs`, 4 `evaluation-results`, 6 `regression-thresholds`, 4 `regression-detection`, 5 `benchmark-versions`, 6 `manual-evaluations`, 5 `deployment-evaluations`, 16 `ab-tests`, 10 `quality-alerts`, 5 `quality-dashboard`, 12 `insights`.

## F8 - User interface, voice and widget (Part 8, 9.3)
Chat interface with SSE streaming, Markdown and code highlighting, citations with tooltips and modal, suggested and follow-up questions, regenerate/edit/retry/rename/share/export conversations, feedback buttons with optional correction, conversation search; voice input/output (push-to-talk, VAD, voice selection, STT/TTS provider adapters), voice agent and telephony (Twilio); embeddable **widget** (38 routes, white-label, suggested questions) and widget SDKs. **Pages:** `/chat`, `/dashboard/voice-agent`, `/dashboard/voice-settings`, `/voice-demo`, `/dashboard/settings/widget`.

## F9 - Public API, SDKs, webhooks, integrations (Part 9, 15)
Versioned **public API** (`/v1`, 30 routes) with API keys (scopes, expiry, rotation, quotas), outbound **webhooks** with delivery history, inbound universal webhooks (Zapier/Make/n8n), Airbyte client, Slack, Microsoft Teams and Discord bots, Twilio SMS/voice, an n8n community node package and a `make-rag-saas` package (`packages/`), SDKs for Python, JavaScript, React and Vue (version 0.1.0 each, in `sdks/`), OpenAPI 3 document (`docs/api/openapi.json`), plugin marketplace (22 routes). **Pages:** `/dashboard/settings/api-keys`, `/dashboard/settings/webhooks`, `/dashboard/settings/integrations`, `/dashboard/settings/connectors`, `/dashboard/api-docs`, `/dashboard/marketplace`.

## F10 - Connectors (40 providers) - see `09_...`
Data connectors for RAG and CRM/ticket extractors, credentials stored per organization (D17): Jira, Zendesk, HubSpot, Salesforce, Shopify, WooCommerce, Mailchimp, Klaviyo, ActiveCampaign, Pipedrive, Zoho, Intercom, Airtable, Asana, Trello, Monday, ClickUp, Linear, Notion, Confluence, GitHub, GitLab, Bitbucket, Google Drive/Docs, OneDrive, Dropbox, Box, Smartsheet, SmartSuite, Wrike, Teamwork, Basecamp, Coda, Miro, DocuSign, Hive, Nifty, Pipefy, Podio, Process Street, Azure DevOps [V: `PROVIDERS` in `connector_credentials.py`]. **Page:** `/dashboard/settings/connectors`.

## F11 - Security, governance and compliance (Part 10) - see `06_...`
Audit logs (HMAC-signed, archived, purged by retention), RBAC with custom roles, security policies, vulnerability and security scans, incidents, data requests (GDPR export/erase), data-breach register, retention policies, encryption key records, prompt-injection and toxicity detection, output guard, MCP firewall, SSRF-safe HTTP client, rate limiting (adaptive), IP trust lists, sandbox environments. **Pages:** `/dashboard/security`.

## F12 - Billing and monetization (Part 12) - see `09_...`
Plans, subscriptions, invoices (PDF, send, remind, void, overdue), prepaid **credits** with packs, auto-refill and spend caps, usage metering and alerts, forecasts, coupons (recorded at redemption, not applied at checkout - D5), payment-provider abstraction with Stripe and Paystack adapters, partner commissions, licences, sales models (SaaS / self-hosted / partner / white-label). **Pages:** `/dashboard/billing`, `/dashboard/partners`.

## F13 - Administration and analytics (Part 11, 20)
Superadmin dashboard (users, organizations, subscriptions, system health), analytics (business, product, technical), aggregates, A/B significance jobs, observability (metrics, tracing, logs, alert rules, incidents). **Pages:** `/admin`, `/dashboard/analytics*`.

## F14 - White-label and resellers (Part 18-19)
Organization branding (logo, colors, brand name, e-mail branding, hide platform branding), custom domain, resellers/sub-clients, widget branding unified. **Pages:** `/dashboard/settings/white-label`, `/dashboard/whitelabel`.

## F15 - Human in the loop (Part 15)
Escalation tickets with SLA deadlines (platform default plus per-organization override), internal notes, human approval requests for sensitive agent actions and workflow human blocks, feedback with corrections, manual evaluation. **Page:** `/dashboard/escalations`. Note: the cahier des charges text for Part 15 was truncated in the original message and never recovered (`docs/CAHIER_DES_CHARGES.md`).

## F16 - Fine-tuning (Part 24) and multimodal (Part 22)
Fine-tuning datasets, jobs (status polled every 10 minutes), evaluations and registered models (17 routes, `/dashboard/fine-tuning*`); one provider is documented as not supportable. Multimodal: images, audio, video indexed into RAG with backfill jobs.

## Gaps between the specification and the product (headline)
* Cahier des charges has **514/515** features (Part 15 truncated; Parts 16-17 do not exist in the text; Parts 18-25 are extension parts added later with an "honest scope" label).
* Not built by decision: SAML (D1/D9), a logo (D3), Black formatter (D6), languages other than fr/en (D7).
* Not completable here: real payment, refunds (BILL-016), coupon application at checkout (D5), chat-platform sandboxes, hosted observability.
