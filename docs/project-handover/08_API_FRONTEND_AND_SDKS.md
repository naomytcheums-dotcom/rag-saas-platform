# 08 - API surface, frontend pages and SDKs

Tags: **[V]** verified from generated inventories or code on 2026-10-12; **[R]** run in project sessions; **[D]** documented only; **[U]** unknown. Exhaustive lists: `annex/api_routes.csv` (983 operations: method, path, tag, operation id, summary, whether OpenAPI declares security), `annex/api_routes_by_tag.json`, `annex/frontend_pages.csv`, `annex/frontend_pages_table.md`. The committed OpenAPI document is `docs/api/openapi.json` (regenerated in PR #25 [R]; `tests/docs/test_api_reference.py` checks that every path documented in `docs/api/*.md` exists in the live schema and that the committed `openapi.json` matches the running app).

## 1. API overview
* **983 operations in 99 tags** under one FastAPI app. The dashboard API has no version prefix; `/v1/*` is the public API (10 distinct paths, 30 operations); `/mcp/v1/*` is MCP; `/scim/v2/*` is SCIM; `/auth/*`, `/admin/*`; `/organizations/{org_id}/...` is the dominant pattern for organization-scoped resources; `/voice/organizations/...`; payment webhooks (`/billing/stripe/webhook`, `/billing/paystack/webhook`); `/metrics`; health endpoints.
* **Authentication kinds:** (1) user JWT in `Authorization: Bearer` plus refresh cookie (dashboard API), (2) organization API key in `X-API-Key` with scopes (public API `/v1`, MCP), (3) agent API keys, (4) widget tokens with a domain allow-list, (5) shared secrets for chat gateways and signature verification for payment webhooks, (6) SCIM bearer tokens, (7) `METRICS_AUTH_TOKEN` for `/metrics`.
* **Authorization:** per-route dependencies (`require_permission`, role guards); a test fails on any unclassified open route.
* **Streaming:** Server-Sent Events for chat (`chat-stream`, 2 routes) with `start / thinking / token / citation / done / error` events and heartbeat comment lines.
* **Errors:** FastAPI validation (422), domain errors mapped to 400/403/404/409, 429 for rate limits, 402/403 for quota or credit exhaustion, 503 when a required service or secret is missing (for example connector credentials without `ENCRYPTION_MASTER_KEY`).

## 2. Route families (by tag, with counts) [V]
| Family | Tags (operations) | Main routes / notes | Auth |
|---|---|---|---|
| Authentication & account | `auth` (32), `account` (15), `sessions` (2), `scim` (10), `admin` (1) | register, login, refresh, logout, 2FA (setup/enable/verify/recovery), WebAuthn, OAuth authorize/callback, SSO discover/authorize/callback, e-mail verification, password forgot/reset, profile, avatar, preferences, delete/restore account | public or JWT; SCIM bearer |
| Organizations & access | `organizations` (9), `teams` (9), `workspaces` (4), `invitations` (4), `organization-settings` (5), `quotas` (2), `user-limits` (3), `usage` (4), `resource-permissions` (4), `RBAC` (12), `custom-domains` (6), `ssl-certificates` (4), `email-domains` (3), `organization-branding` (6), `white-label` (14) | CRUD, members, roles, settings, quotas, branding, domains | JWT + role |
| Documents & knowledge | `documents` (42), `batch-jobs` (5), `external-sources` (5), `reindex-schedules` (4), `documents-sync` (1), `media` (14), `connectors` (3), `search` (1), `citations` (8) | upload, list, versions, tags, imports (url, sitemap, github, drive, docs, notion, confluence, onedrive), reindex, dedupe, media upload/process, connectors PUT/GET/DELETE | JWT + `documents:*` / `integrations:*` |
| Conversations & chat | `conversations` (27), `chat-stream` (2), `conversation-sharing` (2), `feedback` (5), `request-trace` (1), `retrieval-diagnostics` (1), `i18n` (4) | create/list/search/export/share, send message, regenerate/edit/retry, stream, feedback with correction, `GET /responses/{id}/trace` | JWT |
| Agents & tools | `agents` (37), `agent-factory` (2), `agent-api-keys` (4), `agent-traces` (3), `tool-config` (9), `tool-permissions` (4), `custom-tools` (6), `human-approval` (4), `escalations` (7), `autonomous-agents` (19), `workflows` (25), `mcp-servers` (8), `mcp-server` (2), `A2A` (2), `rag-control-plane` (6) | agent CRUD/status/run, factory blueprint and deploy, tool config, workflows CRUD/run/trigger, MCP client and server, A2A | JWT + role; API key (`mcp:tools`) for the MCP server |
| Evaluation & quality | `evaluation-datasets` (12), `questions` (3), `question-sets` (9), `evaluation-jobs` (8), `evaluation-results` (4), `evaluation-comparisons` (2), `comparison-jobs` (17), `benchmark-versions` (5), `regression-thresholds` (6), `regression-detection` (4), `deployment-evaluations` (5), `manual-evaluations` (6), `ab-tests` (16), `quality-alerts` (10), `quality-dashboard` (5), `insights` (12), `analytics` (24) | datasets/questions import-export (`verify_documents`), `POST /datasets/{id}/evaluate`, `/jobs/{id}/results`, `/jobs/{id}/comparison`, `/jobs/{id}/failures`, `/jobs/{id}/failures/categories`, `/datasets/{id}/metrics/{metric}`, alert rules | JWT + `evaluation:*` |
| Billing | `Billing` (44), `coupons` (4), `Sales` (19), `Admin Subscriptions` (16) | plans, subscribe/upgrade/downgrade/cancel/reactivate, checkout, portal, credits (packs, checkout, purchase, transactions), invoices (pdf/send/remind/void/pay), usage (breakdown, forecast, alerts), coupons, webhooks, partner/licence/sales | JWT + `billing:*`; provider signature for webhooks |
| Integrations & channels | `Integrations` (23), `Webhooks` (7), `Slack Integration` (7), `Teams Integration` (5), `Discord Integration` (6), `telephony` (10), `voice` (5), `voice-messages` (4), `voice-settings` (3), `Widget` (38), `crm` (36), `Public API` (30), `API Versioning` (2) | integration connections/logs/mappings, webhook CRUD/test/deliveries, chat bots, Twilio, widget config and embed, CRM extractors (36 routes, each behind `connector_scope`), public `/v1` | mixed |
| Admin & operations | `Admin Dashboard` (19), `Admin Organizations` (10), `Admin Users` (10), `Observability` (19), `monitoring` (3), `Compliance` (13), `audit` (12), `Security scanning` (12), `Encryption` (4), `Notifications` (12), `Notification Templates` (7), `sandbox` (4) | superadmin management, health/queues/resources, logs, metrics, audit logs, GDPR, scans, key rotation, notification templates | superadmin or `audit_logs:*`, `security:*` |
| Marketplace & fine-tuning | `Plugin marketplace` (22), `fine-tuning` (17) | plugins, versions, reviews, installs; datasets, jobs, models | JWT |

Selected contracts [V]: `PUT /organizations/{org_id}/connectors/{provider}` takes `{fields: {...}}`, validates (https, public address, vendor suffix, strict identifier kinds) and never returns secret values (only which fields are set); `GET /organizations/{org_id}/connectors` lists the 40 providers with `connected`, `required_fields`, `works_without_credentials`. The 36 CRM routes and the 7 importer routes answer **403 "has not connected"** until the organization stores its credentials.

## 3. Frontend (Next.js 16 App Router, React 19, TypeScript, Tailwind CSS)
### 3.1 Structure [V]
* `frontend/app/**/page.tsx`: 64 pages (table below). `frontend/components/`: about 90 shared components plus domain folders (`ab-tests`, `analytics`, `auth`, `autonomous`, `dashboard`, `eval`, `figma`, `fine-tuning`, `integrations`, `landing`, `media`, `partners`, `plugins`, `whitelabel`, `workflows`). `frontend/lib/`: `api.ts` (fetch wrapper), `auth.tsx` (auth context and guard), `i18n.tsx`, `branding-context.tsx`, `useCurrentOrg.ts`, `useRealChat.ts`, `hooks/` and `services/` per domain, voice helpers. `frontend/widget/`: vanilla embed script, iframe page, CSS.
* **API client** (`lib/api.ts`): base URL from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`); sends `Authorization: Bearer <access_token from localStorage>` and cookies (`credentials: include`); on a `401` it calls `POST /auth/refresh` once (one shared in-flight promise; CSRF header from the `csrf_token` cookie) and retries; throws `ApiError(status, detail)`; helpers for JSON, multipart, single-file upload and raw fetch; `fileUrl()` builds download URLs.
* **Route protection:** there is **no Next.js middleware**. Protection is a **client-side guard** (`lib/auth.tsx`: when loading has finished and there is no user, `router.replace("/login")`). The server still enforces every permission; the pages are static shells.
* **State:** React context (auth, branding, current organization via `useCurrentOrg`); per-domain hooks that call services; no global store library.
* **i18n:** `fr` and `en` only (D7); sources in `locales/<code>/common.json` synced into `frontend/lib/locales` by `scripts/sync_frontend_locales.py` (a test checks that the bundled copy matches the sources); language menu with flags.
* **Chat page** (`/chat`): `ChatSidebar`, `ChatComposer`, `MessageBubble`/`ChatMarkdown` (sanitised Markdown + code highlighting), citation components (list, tooltip, modal), suggested and follow-up questions, feedback buttons, voice components; uses the real API through `useRealChat` (an old mock chat was removed).
* **Tests:** Vitest component tests beside the pages; Playwright smoke tests in `e2e/` (12 of 12 passing in Chrome on 2026-10-11 [R]); nightly workflow `.github/workflows/e2e.yml`.
### 3.2 Pages and their backend wiring [V: generated]
A page that shows "(via shared components/hooks)" calls the API through `components/<domain>/*`, `lib/hooks/*` or `lib/services/*` rather than directly. Wiring was verified by static call-site extraction, **not by clicking through every page against a live backend** (only the Playwright smoke path and the `ImportSources`/connectors tests exercised screens). Observations: `/maquette` is a Figma reproduction of a landing page with 7 of 12 desktop sections and no tablet/mobile version; `/dashboard/whitelabel` (5 lines) and `/dashboard/analytics` (5 lines) are thin wrappers; `/voice-demo` is a demo page.

| Route | Audience | Lines | Backend calls made directly by the page (others go through `components/`, `lib/hooks`, `lib/services`) |
|---|---|---:|---|
| `/2fa-lockout-recovery` | public | 16 | (via shared components/hooks) |
| `/admin` | superadmin | 681 | /admin/logs{}, /admin/monitoring/health, /admin/monitoring/queues, /admin/monitoring/resources ... |
| `/chat` | authenticated | 130 | (via shared components/hooks) |
| `/dashboard/ab-tests/[id]` | authenticated | 9 | (via shared components/hooks) |
| `/dashboard/ab-tests` | authenticated | 34 | (via shared components/hooks) |
| `/dashboard/agents/factory` | authenticated | 130 | /organizations/{}/factory/blueprint, /organizations/{}/factory/deploy |
| `/dashboard/agents/new` | authenticated | 113 | /organizations/{}/agents |
| `/dashboard/agents` | authenticated | 115 | /agents/{}/{}, /agents/{}, /organizations/{}/agents |
| `/dashboard/analytics/business` | authenticated | 12 | (via shared components/hooks) |
| `/dashboard/analytics` | authenticated | 5 | (via shared components/hooks) |
| `/dashboard/analytics/product` | authenticated | 25 | (via shared components/hooks) |
| `/dashboard/analytics/technical` | authenticated | 25 | (via shared components/hooks) |
| `/dashboard/api-docs` | authenticated | 75 | (via shared components/hooks) |
| `/dashboard/autonomous-agents/[id]` | authenticated | 13 | (via shared components/hooks) |
| `/dashboard/autonomous-agents` | authenticated | 41 | (via shared components/hooks) |
| `/dashboard/billing` | authenticated | 541 | /billing/plans, /billing/plans/{}, /organizations/{}/billing/cancel, /organizations/{}/billing/checkout ... |
| `/dashboard/documents` | authenticated | 135 | /documents/{}, /organizations/{}/documents |
| `/dashboard/escalations` | authenticated | 145 | {}${filter ? , {}/{}, {}/{}/assign, {}/{}/notes ... |
| `/dashboard/eval/[datasetId]/jobs/[jobId]` | authenticated | 45 | (via shared components/hooks) |
| `/dashboard/eval/[datasetId]` | authenticated | 37 | (via shared components/hooks) |
| `/dashboard/eval/evolution` | authenticated | 171 | /organizations/{}/agents, /organizations/{}/agents/{}/retrieval-config/apply, /organizations/{}/datasets, /organizations/{}/evolution/retrieval/run |
| `/dashboard/eval` | authenticated | 35 | (via shared components/hooks) |
| `/dashboard/eval/runs/[runId]/comparison` | authenticated | 68 | /jobs/{}/comparison?with={} |
| `/dashboard/fine-tuning/datasets` | authenticated | 25 | (via shared components/hooks) |
| `/dashboard/fine-tuning/jobs/[id]` | authenticated | 13 | (via shared components/hooks) |
| `/dashboard/fine-tuning/jobs` | authenticated | 35 | (via shared components/hooks) |
| `/dashboard/fine-tuning/models` | authenticated | 19 | (via shared components/hooks) |
| `/dashboard/fine-tuning` | authenticated | 39 | (via shared components/hooks) |
| `/dashboard/insights` | authenticated | 123 | {}/feedback/analysis, {}/insights/cost-per-answer?days={}, {}/insights/cost-per-user?days={}, {}/insights/documentation-gaps?days={} ... |
| `/dashboard/marketplace` | authenticated | 151 | (via shared components/hooks) |
| `/dashboard/media/[id]` | authenticated | 13 | (via shared components/hooks) |
| `/dashboard/media` | authenticated | 55 | (via shared components/hooks) |
| `/dashboard` | authenticated | 318 | /organizations/{}/agents, /organizations/{}/api-keys, /organizations/{}/documents, /organizations/{}/webhooks |
| `/dashboard/partners` | authenticated | 22 | (via shared components/hooks) |
| `/dashboard/profile` | authenticated | 518 | /account/avatar, /account/change-password, /account/me, /account/preferences ... |
| `/dashboard/quality` | authenticated | 173 | {}/history, {}/metrics, {}/rules, {}/rules/{} ... |
| `/dashboard/quality-scores` | authenticated | 118 | {}/dashboard?period={}, {}/responses?limit=25, {}/trends?period={}&metric=groundedness_score |
| `/dashboard/security` | authenticated | 633 | /compliance/consent, /compliance/consent/{}, /compliance/status, /encryption/rotate-keys ... |
| `/dashboard/settings/api-keys` | authenticated | 243 | /api-keys/{}/quota/status, /api-keys/{}/rotate, /api-keys/scopes, /organizations/{}/api-keys ... |
| `/dashboard/settings/connectors` | authenticated | 165 | /organizations/{}/connectors, /organizations/{}/connectors/{} |
| `/dashboard/settings/integrations` | authenticated | 148 | /organizations/{}/integrations/{}, /organizations/{}/integrations/discord/configure, /organizations/{}/integrations/slack/auth, /organizations/{}/integrations/teams/configure ... |
| `/dashboard/settings/llm-config` | authenticated | 148 | /organizations/{}/llm-config, /organizations/{}/llm-config/{} |
| `/dashboard/settings/organization` | authenticated | 126 | /organizations/{}, /organizations/{}/members, /organizations/{}/members/{}, /organizations/{}/members/invite |
| `/dashboard/settings/webhooks` | authenticated | 237 | /organizations/{}/webhooks, /webhooks/{}, /webhooks/{}/test, /webhooks/{} ... |
| `/dashboard/settings/white-label` | authenticated | 103 | /organizations/{}/branding |
| `/dashboard/settings/widget` | authenticated | 174 | /organizations/{}/widget/config, /organizations/{}/widget/config/name, /organizations/{}/widget/logo, /organizations/{}/widget/position ... |
| `/dashboard/teams` | authenticated | 154 | /organizations/{}/teams, /organizations/{}/workspaces, /organizations/{}/teams, /organizations/{}/workspaces ... |
| `/dashboard/voice-agent` | authenticated | 148 | /voice/organizations/{}/agent?{} |
| `/dashboard/voice-settings` | authenticated | 35 | /organizations/{}/agents |
| `/dashboard/whitelabel` | authenticated | 5 | (via shared components/hooks) |
| `/dashboard/workflows/[id]` | authenticated | 31 | (via shared components/hooks) |
| `/dashboard/workflows` | authenticated | 72 | (via shared components/hooks) |
| `/forgot-password` | public | 46 | /auth/password/forgot |
| `/invitations/accept` | public | 83 | /invitations/accept |
| `/login` | public | 89 | /auth/2fa/verify-login |
| `/maquette` | public | 29 | (via shared components/hooks) |
| `/oauth-callback` | public | 90 | (via shared components/hooks) |
| `/` | public | 24 | (via shared components/hooks) |
| `/reactivate-consent` | public | 17 | (via shared components/hooks) |
| `/register` | public | 54 | (via shared components/hooks) |
| `/reset-password` | public | 55 | /auth/password/reset |
| `/restore-account` | public | 15 | (via shared components/hooks) |
| `/verify-email` | public | 64 | /auth/verify-email/confirm, /auth/verify-email/request |
| `/voice-demo` | public | 52 | (via shared components/hooks) |

## 4. SDKs and developer surfaces [V]
| Package | Location | Version | Contents | Published? |
|---|---|---|---|---|
| Python `rag-saas-sdk` | `sdks/python` (`rag_saas_sdk/client.py`, `errors.py`, `types.py`, tests) | 0.1.0 | `RagSaasClient(api_key, base_url=..., timeout=30)`; resources: chat (`send`, `stream`), documents (`upload`, `list`, `query`), agents (`run`, `list`), usage, analytics, embeddings (`generate`), conversations (`list`), knowledge bases (`list`, `create`); context manager | **[U]** no evidence of publication to PyPI |
| JavaScript `rag-saas-sdk` | `sdks/js` | 0.1.0 | same surface in TypeScript, Vitest tests | **[U]** npm publication not evidenced |
| React widget `@rag-saas/widget-react` | `sdks/react` | 0.1.0 | `RAGWidget` component | [U] |
| Vue widget `@rag-saas/widget-vue` | `sdks/vue` | 0.1.0 | Vue component | [U] |
| n8n node | `packages/n8n-nodes-rag-saas` | n/a | community node for n8n | [U] |
| `make-rag-saas` | `packages/make-rag-saas` | n/a | Make.com app definition | [U] |
| Embeddable widget | `frontend/widget` | n/a | `embed.js` + iframe, configured in `/dashboard/settings/widget` (domain allow-list, branding, suggested questions) | served by the frontend |
**Compatibility check performed:** every `/v1/...` path used by the Python SDK exists in the current OpenAPI (10 of 10, e.g. `/v1/chat`, `/v1/documents`, `/v1/search`, `/v1/agents/run`, `/v1/embed`, `/v1/usage`, `/v1/conversations`, `/v1/knowledge-bases`, `/v1/analytics`, `/v1/agents`) [V]. **Documentation/behaviour gaps:** both SDKs default to `base_url="https://api.ragsaasplatform.com"`, a domain that is not shown to be owned or deployed (the documented live API is `rag-saas-api-sjsm.onrender.com`); versions are all 0.1.0, no changelog or release process was found; whether the SDK request/response shapes exactly match the server models beyond path existence was **not** verified field by field. A library in the repository is not the same as a published, versioned package a customer can install; treat the SDKs as **present and path-compatible, not released**.

## 5. Public API (`/v1`) contract in brief [V]
Authentication `X-API-Key` (organization key with scopes, expiry, rotation, quota; rate limited, usage metered); operations: chat (`POST /v1/chat`, streaming variant), search, documents upload/list, agents list/run, embeddings, usage, analytics, conversations, knowledge bases. Implemented in `api/services/public_api.py` (`handle_public_chat` runs `AgentOrchestrator` and is shared with the Slack/Teams/Discord bots) and `api/routers` under tag `Public API`.

## 6. What is incomplete or ambiguous on the client side
* Client-side-only route guard (acceptable but worth a server-side middleware for SEO/UX and defence in depth).
* Access token kept in `localStorage`.
* Thin pages whose backing API calls were not exercised end to end against a live server (autonomous agents, fine-tuning, media, marketplace, partners, A/B tests).
* Landing page "maquette" is partial; no logo (D3).
* Interface languages restricted to fr/en by decision; the older Google Translate widget was removed after freezing the page.
