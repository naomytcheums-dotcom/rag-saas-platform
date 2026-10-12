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