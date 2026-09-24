# RAG SaaS Platform

A multi-tenant, production-oriented SaaS platform for building
retrieval-augmented generation products: document ingestion, hybrid
search, chat, autonomous agents, workflows, fine-tuning, analytics,
billing, white-labeling, and a full admin/security surface — built on
top of a real, evaluated RAG pipeline (see below).

**Status: feature-complete across 25 development parts (Parties 1-25),
plus an ongoing Phase 5 of platform-maturity work (20 étapes as of
2026-09-24): MCP (client + server, including custom and per-run tools),
a visual workflow builder (React Flow) with undo/redo and a richer
human-approval editor, enterprise SSO via generic OIDC, a second billing
provider (Paystack, alongside Stripe), an application-level Redis cache
and measured DB indexing, Eval Lab's own dedicated frontend with real
failure-category analysis AND job-comparison, a Sandbox Environment, a
full RBAC granulaire layer wired on 45 routers, 36 real CRM/connector
integrations (Salesforce, HubSpot, Jira, Zendesk, Pipedrive, Linear,
Asana, Trello, Airtable, Dropbox, Box, ClickUp, Intercom, Zoho, Shopify,
WooCommerce, DocuSign, Monday, GitLab, Bitbucket, Azure DevOps,
Basecamp, Wrike, Smartsheet, Coda, Miro, Podio, Pipefy, Hive, Teamwork,
Nifty, SmartSuite, Process Street, ActiveCampaign, Mailchimp, Klaviyo),
and notification real-time replay.**
See [`docs/CAHIER_DES_CHARGES.md`](docs/CAHIER_DES_CHARGES.md) for
Parties 1-25's full, itemized build history (audits, real bugs found
and fixed, test counts), and [`ROADMAP.md`](ROADMAP.md) for the Phase 5
étape-by-étape log (same discipline: every gap traced or fixed, never
silently dropped).

## What this is

This repository actually contains two things:

1. **`src/`** — the original single-tenant RAG demo this project started
   as: a FastAPI-docs Q&A assistant with a hand-evaluated retrieval
   pipeline, an honest failure analysis, and a Streamlit dashboard. Its
   own methodology and results are documented in
   [`src/README.md`](src/README.md) and remain accurate — nothing there
   was changed. Its retrieval/chunking/embedding techniques (hybrid
   BM25+semantic search, Reciprocal Rank Fusion, cross-encoder
   reranking) are the same ones the platform below builds on at
   multi-tenant scale.
2. **`api/` + `frontend/`** — the actual product: a multi-tenant RAG SaaS
   platform with organizations, billing, auth, a full document/chat/agent
   pipeline, and a complete operator/admin surface. This is what the rest
   of this README documents.

## Core capabilities

- **Multi-tenant organizations** — orgs, teams, workspaces, members,
  role-based access control (RBAC) with 52 granular permissions, SSO
  (enterprise, generic OIDC — Azure AD, Okta, or any OIDC-conformant
  IdP), two-factor auth, WebAuthn, invitations.
- **Document pipeline** — upload, ingestion, chunking, embeddings, hybrid
  search (BM25 + semantic + reranking), citations, external source
  connectors (Slack, Teams, Discord, n8n, Airbyte, and more), batch jobs.
- **Chat & conversations** — streaming chat with rendered Markdown and
  syntax-highlighted code blocks, inline citations, conversation sharing,
  feedback capture, voice messages and voice settings, a public/embeddable
  widget.
- **Agents** — configured chatbot-persona agents (`agents.py`,
  `custom_tools.py`, `tool_config.py`, `tool_permissions.py`) *and*
  genuinely separate **autonomous agents** (`autonomous_agents.py`) that
  plan and execute multi-step goals with real tool-calling loops, memory,
  bounded agent-to-agent collaboration, guardrails, and per-step/per-agent
  USD cost tracking — see [`docs/autonomous/`](docs/autonomous/).
- **Workflows** — multi-step orchestration (`workflows.py`) built on
  Celery for background execution, with a visual, drag-and-drop builder
  (React Flow) in the frontend.
- **Agent tools & MCP** — agent function-calling/tool-calling loops, and
  the Model Context Protocol in both directions: this platform as an MCP
  *server* (exposing its own tool registry to external MCP clients) and
  as an MCP *client* (registering and calling external MCP servers).
- **Eval Lab** — evaluation datasets, jobs, results, comparisons,
  deployment evaluations, manual evaluations, regression detection with
  configurable thresholds, a quality dashboard, benchmark versions, and
  a dedicated frontend (`/dashboard/eval`) with real failure-category
  analysis (retrieval vs. generation vs. suspected hallucination, from
  actually-recorded failures and metrics — never a placeholder label).
- **Fine-tuning** — dataset upload and validation (JSONL), job submission
  to OpenAI and Mistral (Anthropic has no public fine-tuning API — this
  gap is documented, not faked), fine-tuned model deployment, and
  evaluation of fine-tuned models through the same Evaluation Lab used
  for regular model comparisons — see [`docs/fine-tuning/`](docs/fine-tuning/).
- **Media & vision** — media asset processing, vision-in-documents,
  object detection (YOLOv8, local inference), and CLIP-based visual
  search (image-to-image and text-to-image) — see
  [`docs/media/`](docs/media/).
- **A/B testing** — experiment configuration and analysis for prompts,
  models, and retrieval settings — see [`docs/ab-testing/`](docs/ab-testing/).
- **Analytics & observability** — usage analytics, audit logs, agent
  traces, observability endpoints, human-approval workflows — see
  [`docs/analytics/`](docs/analytics/), [`docs/monitoring/`](docs/monitoring/).
- **Billing & sales** — subscriptions, quotas, usage-based billing, two
  independent payment providers (Stripe and Paystack, behind one shared
  provider interface), a partner/sales program — see
  [`docs/billing/`](docs/billing/), [`docs/sales/`](docs/sales/).
- **Notifications** — in-app + email notifications with per-user
  preferences, real delivery tracking, and an unread-count endpoint
  backed by a real composite index (`notifications(user_id, read_at)`).
- **API Platform & SDKs** — organization-scoped public API keys (hashed,
  never stored in plaintext), granular scopes, rotation, rate limits and
  quotas per key, and client SDKs in
  [Python](sdks/python/README.md), [JavaScript](sdks/js/README.md),
  [React](sdks/react/README.md) and [Vue](sdks/vue/README.md).
- **Observability & performance** — agent traces, audit logs, per-request
  token/cost tracking, live retrieval diagnostics, and an
  application-level Redis cache (fail-open, same discipline as the
  rate limiter) on top of measured, audited DB indexing — see
  [`docs/monitoring/`](docs/monitoring/).
- **White-labeling & branding** — custom domains, SSL certificates,
  organization branding — see [`docs/whitelabel/`](docs/whitelabel/).
- **Marketplace & plugins** — a plugin system and marketplace for
  extending the platform — see [`docs/plugins/`](docs/plugins/),
  [`docs/marketplace/`](docs/marketplace/).
- **Security & compliance** — encryption, compliance tooling, security
  scanning, audit trails, RBAC — see [`docs/security/`](docs/security/).
- **Admin dashboard** — organization/user/subscription management for
  platform operators — see [`docs/admin/`](docs/admin/).
- **CI/CD & integrations** — the platform's own CI tooling docs and a
  universal integrations layer (Slack, Teams, Discord, Twilio, webhooks,
  n8n, Airbyte) — see [`docs/ci/`](docs/ci/), [`docs/integrations/`](docs/integrations/).
- **CRM & business connectors** — 36 real, provider-specific extraction
  modules (each with its own real auth convention: Bearer, Basic, custom
  header, query param, GraphQL) exposing a unified
  `POST /organizations/{org_id}/crm/{provider}/import` endpoint that
  ingests each provider's records as real documents into the RAG
  pipeline. Covers Salesforce, HubSpot, Jira, Zendesk, Pipedrive,
  Linear, Asana, Trello, Airtable, Dropbox, Box, ClickUp, Intercom,
  Zoho, Shopify, WooCommerce, DocuSign, Monday, GitLab, Bitbucket,
  Azure DevOps, Basecamp, Wrike, Smartsheet, Coda, Miro, Podio,
  Pipefy, Hive, Teamwork, Nifty, SmartSuite, Process Street,
  ActiveCampaign, Mailchimp, Klaviyo.
- **Granular RBAC** — 52 fine-grained `resource:action` permissions
  (13 resources × 4 actions) with real FastAPI dependencies
  (`require_permission("documents:write")`) wired on 45 routers
  (~250 endpoints), plus real default permissions per fixed role
  (Owner/Admin/Manager/Member/Viewer) so a Member keeps real read/write
  access without needing a hand-crafted CustomRole first. Resource-level
  patterns (`require_dataset_admin`, `require_agent_manager`, etc.)
  remain as-is on the routers that need them — more granular, more
  secure, not replaced.
- **Sandbox Environment** — a real, per-organization isolated dev/test
  environment with TTL and a reset endpoint — see `api/routers/sandbox.py`.
- **Zapier / Make / n8n** — 6 real inbound actions
  (`ingest_document`, `log_only`, `create_agent`, `create_conversation`,
  `send_notification`, `trigger_workflow`) triggered by external
  systems POSTing to an organization-scoped webhook — gives instant
  reach to Zapier's 5000+ apps without hand-coding each connector.
- **Real-time notification replay** — the SSE stream sends an initial
  snapshot of unread notifications before streaming new ones, so a
  reconnecting client never misses what happened while offline.

The API surface spans 89 routers under [`api/routers/`](api/routers/);
the frontend has 17 top-level dashboard sections under
[`frontend/app/dashboard/`](frontend/app/dashboard/).

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI, SQLAlchemy 2.0 (async), PostgreSQL (Supabase), Alembic |
| Background jobs | Celery + Redis |
| LLM access | [litellm](https://github.com/BerriAI/litellm) — a single abstraction over Anthropic, OpenAI, Mistral, and other providers |
| Frontend | Next.js, React, TypeScript |
| Frontend tests | Vitest |
| Backend tests | pytest |
| Object storage | S3-compatible |
| Vision / media | YOLOv8 (`ultralytics`, local inference), CLIP (`openai/clip-vit-base-patch32`) + faiss-cpu |

## Getting started

For a hosted/SaaS deployment vs. self-hosting, see
[`docs/install/SAAS.md`](docs/install/SAAS.md) and
[`docs/install/SELF_HOSTED.md`](docs/install/SELF_HOSTED.md).

Quick self-hosted start:

```bash
cp .env.example .env
# fill in the required secrets in .env (see docs/install/ENVIRONMENT.md)
./install.sh
docker compose -f docker-compose.selfhosted.yml up -d
```

Full installation, environment variables, database setup, and upgrade
paths are documented in [`docs/install/`](docs/install/).

## Documentation

Full documentation lives under [`docs/`](docs/) — start at
[`docs/index.md`](docs/index.md). It's organized as:

- [`docs/user/`](docs/user/) — end-user guides (getting started, using
  chat, documents, search).
- [`docs/admin/`](docs/admin/) — organization and platform administration.
- [`docs/developer/`](docs/developer/) — architecture, API usage, SDKs
  ([Python](sdks/python/README.md), [JavaScript](sdks/js/README.md),
  [React](sdks/react/README.md), [Vue](sdks/vue/README.md)),
  integrations, webhooks.
- [`docs/install/`](docs/install/) — deployment, environment, upgrades,
  backups.
- [`docs/api/`](docs/api/) — REST API reference, including a live
  OpenAPI export ([`docs/api/openapi.json`](docs/api/openapi.json)),
  Swagger, and Redoc.
- [`docs/advanced/`](docs/advanced/) — the RAG pipeline internals
  (chunking, embeddings, retrieval, reranking) and links into each major
  subsystem's own detailed docs (autonomous agents, fine-tuning, media,
  A/B testing).
- [`docs/tutorials/`](docs/tutorials/) and [`docs/faq/`](docs/faq/) —
  task-oriented walkthroughs and common questions.
- [`docs/diagrams/`](docs/diagrams/) — architecture, database, RAG
  pipeline, auth flow, deployment, and multi-tenancy diagrams.

See also [`ARCHITECTURE.md`](ARCHITECTURE.md) for a system-level overview,
[`ROADMAP.md`](ROADMAP.md) for what's planned, and
[`GLOSSARY.md`](GLOSSARY.md) for platform-specific terminology.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Security issues should be
reported per [`SECURITY.md`](SECURITY.md).

## License

MIT — see [`LICENSE`](LICENSE).

## Project history

This platform was built incrementally across 25 documented development
parts, each with its own audit, real (never fabricated) test results,
and honest documentation of gaps and limitations. The full history —
including which features were genuinely new vs. extensions of existing
infrastructure, every real bug found and fixed, and every deliberate
scope decision — is in [`docs/CAHIER_DES_CHARGES.md`](docs/CAHIER_DES_CHARGES.md).

The project's origin as a single-tenant, hand-evaluated RAG demo — with
its own real retrieval-quality measurements and honestly-documented
methodology caveats — is preserved at [`src/README.md`](src/README.md).
