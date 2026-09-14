# RAG SaaS Platform

A multi-tenant, production-oriented SaaS platform for building
retrieval-augmented generation products: document ingestion, hybrid
search, chat, autonomous agents, workflows, fine-tuning, analytics,
billing, white-labeling, and a full admin/security surface — built on
top of a real, evaluated RAG pipeline (see below).

**Status: feature-complete across 25 development parts (Parties 1-25).**
See [`docs/CAHIER_DES_CHARGES.md`](docs/CAHIER_DES_CHARGES.md) for the
full, itemized build history of every part, including audits, real bugs
found and fixed, and test counts.

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
  role-based access control (RBAC), resource-level permissions, SSO
  (enterprise SAML/OAuth), two-factor auth, WebAuthn, invitations.
- **Document pipeline** — upload, ingestion, chunking, embeddings, hybrid
  search (BM25 + semantic + reranking), citations, external source
  connectors (Slack, Teams, Discord, n8n, Airbyte, and more), batch jobs.
- **Chat & conversations** — streaming chat, conversation sharing,
  feedback capture, voice messages and voice settings, a public/embeddable
  widget.
- **Agents** — configured chatbot-persona agents (`agents.py`,
  `custom_tools.py`, `tool_config.py`, `tool_permissions.py`) *and*
  genuinely separate **autonomous agents** (`autonomous_agents.py`) that
  plan and execute multi-step goals with real tool-calling loops, memory,
  bounded agent-to-agent collaboration, guardrails, and per-step/per-agent
  USD cost tracking — see [`docs/autonomous/`](docs/autonomous/).
- **Workflows** — multi-step orchestration (`workflows.py`) built on
  Celery for background execution.
- **Evaluation & quality** — evaluation datasets, jobs, results,
  comparisons, deployment evaluations, manual evaluations, regression
  detection with configurable thresholds, a quality dashboard, benchmark
  versions.
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
- **Billing & sales** — subscriptions, quotas, usage-based billing, a
  partner/sales program — see [`docs/billing/`](docs/billing/),
  [`docs/sales/`](docs/sales/).
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
