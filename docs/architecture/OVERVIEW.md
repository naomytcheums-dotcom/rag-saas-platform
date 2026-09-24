# System Overview

Vue d ensemble des composants, de la stack et des flux principaux.
Pour le detail RAG, voir DATA_FLOW.md. Pour la securite, voir SECURITY.md.
Pour le legacy src/, voir LEGACY.md.

Voir aussi le diagramme haut-niveau : ARCHITECTURE.md (racine).

## Composants

### Frontend (frontend/)

- Next.js (App Router), TypeScript, TailwindCSS.
- 17 sections dashboard : chat, documents, agents, workflows,
  evaluation, fine-tuning, media, billing, admin, security, MCP...
- Branding dynamique : BrandingProvider + BrandingApplier.
- Streaming : SSE pour chat/agents.
- Widget embarquable : composant React autonome.

### Backend (api/)

- FastAPI, async partout (SQLAlchemy 2.0 async).
- 92 routers.
- ORM : SQLAlchemy 2.0 async, migrations Alembic.
- Auth : sessions + API keys + SSO + 2FA + WebAuthn.
- LLM : abstraction via litellm, support Anthropic/OpenAI/Mistral + BYOK.

### Background jobs (Celery + Redis)

- Worker Celery : ingestion, evals, workflow runs, reindex, notifications, backups.
- Transaction-mode pooler Supabase (port 6543).
- 28 fichiers de taches migres vers api/tasks/_db.py.

### Stockage

- PostgreSQL (Supabase) + pgvector.
- S3/R2 pour documents, media, datasets.
- Redis pour Celery broker + cache.

### MCP (Model Context Protocol)

- Client : consomme des serveurs MCP externes.
- Serveur : expose les tools custom.

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Frontend | Next.js, TypeScript, TailwindCSS |
| Backend | FastAPI, Python 3.13, SQLAlchemy 2.0 async |
| DB | PostgreSQL (Supabase) + pgvector |
| Migrations | Alembic |
| Background | Celery + Redis |
| Storage | S3 / Cloudflare R2 |
| LLM | litellm (Anthropic, OpenAI, Mistral, BYOK) |
| Auth | Sessions + API keys + SSO + 2FA + WebAuthn |
| Multi-tenant | RLS PostgreSQL + checks applicatifs |

## Flux principaux

Voir DATA_FLOW.md pour le detail :
- Ingestion de documents.
- Chat RAG.
- Agents.
- Workflows.

## Securite

Voir SECURITY.md.

## Deploiement

Voir docs/install/.
