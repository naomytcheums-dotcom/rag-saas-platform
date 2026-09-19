"""Real fix (2026-09-19, found via audit): every *_tasks.py module used
to create its OWN separate `create_engine(...)` call, each with
SQLAlchemy's default pool (pool_size=5, max_overflow=10 -- up to 15
connections EACH). With 18 such modules all imported by
`api/tasks/celery_app.py`'s own `include=[...]` list, the real,
aggregate worst case was 18 x 15 = 270 possible connections against a
Supabase session-mode pooler that caps at 15 TOTAL, across every
process (this module, the async API engine, everything). Shrinking each
engine's own pool individually would still leave 18 separate pools
fighting over the same budget -- the real fix is ONE shared engine,
same principle as `api/database.py`'s own async engine having a single,
explicit `pool_size`/`max_overflow`.

`pool_size=3, max_overflow=2` (5 max) matches the bound already applied
to the async engine (`api/database.py`) -- a Celery worker in this
deployment runs `--pool=solo --concurrency=1` (see
docs/deployment/GITHUB_ACTIONS.md), so only one task executes at a
time in practice; this budget leaves real headroom for that to change
later without silently re-introducing the same connection-exhaustion
risk this fix closes."""

from sqlalchemy import create_engine

from api.config import settings

sync_engine = create_engine(
    settings.DATABASE_URL.replace("+asyncpg", ""),
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=2,
)
