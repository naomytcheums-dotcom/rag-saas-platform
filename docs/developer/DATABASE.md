# Database

PostgreSQL (Supabase), accessed via SQLAlchemy 2.0 async models under
`api/models/`, one module per feature area (e.g.
`api/models/autonomous_agent.py`, `api/models/fine_tuning.py`).
Migrations are managed with Alembic under `api/alembic/versions/`.

## Multi-tenancy

Nearly every tenant-scoped table carries an `org_id` foreign key, and
most enable row-level security (RLS) at the database level as a second
enforcement layer beyond application-level checks — see
[`docs/security/PARTIE_10_SECURITY.md`](../security/PARTIE_10_SECURITY.md).

## Migration history highlights

Migrations are sequential (`0001`...`0108` as of the fine-tuning part).
Recent examples:

- `0105_clip_visual_search.py` — adds `MediaAsset.clip_embedding`.
- `0106_autonomous_agents.py` — 5 autonomous-agent tables.
- `0107_autonomous_agent_cost_tracking.py` — adds real cost-tracking
  columns.
- `0108_fine_tuning.py` — 4 fine-tuning tables, RLS enabled.

## Running migrations

```bash
cd api
alembic upgrade head
```

See [Database Setup](../install/DATABASE_SETUP.md) for a fresh install.

## Schema diagram

See [`docs/diagrams/DATABASE.md`](../diagrams/DATABASE.md) for a
rendered overview of the major tables and their relationships.

## Naming conventions

Object-storage key columns are always named `file_key` (not
`file_path`) across every model that has one — `Document.file_key`,
`MediaAsset.file_key`, `FineTuningDataset.file_key` — matching this
codebase's established S3-key convention.
