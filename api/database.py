"""
Async SQLAlchemy 2.0 engine/session setup. One engine per process, one
AsyncSession per request via the get_db dependency (api/dependencies.py) --
never a global session shared across requests, which would leak state
between unrelated users under concurrency.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from api.config import settings

# Real production error found live (2026-09-17, Render deploy log):
# asyncpg.exceptions.InternalServerError: (EMAXCONNSESSION) max clients
# reached in session mode - max clients are limited to pool_size: 15.
# DATABASE_URL points at Supabase's SESSION-mode pooler (port 5432),
# which caps the TOTAL number of concurrent client connections across
# EVERY process talking to it -- not per-app, per-database-wide.
# SQLAlchemy's own defaults (pool_size=5, max_overflow=10) mean a
# single process can alone open up to 15 connections at peak, exactly
# the pooler's entire real budget -- leaving zero room for anything
# else genuinely connected at the same time (a local dev server, a
# one-off admin script, a future separate Celery worker process, each
# with their own engine and their own pool). Set explicitly smaller and
# conservative rather than left at SQLAlchemy's defaults, which were
# never sized against this specific pooler's real, tight ceiling.
# Real fix (2026-09-24, found when Celery --concurrency=16 hit Supabase's
# session-mode 15-connection cap): use the TRANSACTION-mode pooler
# (port 6543) for the async app engine. Falls back to DATABASE_URL if
# unset (e.g. local dev without a Supabase transaction-mode port).
#
# IMPORTANT: pgBouncer in transaction mode does NOT support prepared
# statements -- asyncpg's own caches MUST be disabled or every query
# fails with "prepared statement ... already exists".
_engine_url = settings.DATABASE_URL_TRANSACTION or settings.DATABASE_URL
_engine_connect_args = {}
if settings.DATABASE_URL_TRANSACTION:
    _engine_connect_args = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }

import os as _os

# Hackathon fix: allow forcing pool_size/max_overflow via env vars so
# Render Free can override the defaults without a code change. The
# default remains 5/10 as patched above.
_pool_size = int(_os.environ.get("SQLALCHEMY_POOL_SIZE", "5"))
_max_overflow = int(_os.environ.get("SQLALCHEMY_MAX_OVERFLOW", "10"))
_pool_timeout = int(_os.environ.get("SQLALCHEMY_POOL_TIMEOUT", "60"))

engine = create_async_engine(
    _engine_url,
    pool_pre_ping=True,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    pool_timeout=_pool_timeout,
    connect_args=_engine_connect_args,
)

try:
    _port = engine.url.port
except Exception as _exc:
    _port = f"<err>"
print(f"[RUNTIME_DB_CONFIG] source=MAIN_DATABASE pool_size={_pool_size} max_overflow={_max_overflow} pool_timeout={_pool_timeout} port={_port}", flush=True)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency (`Depends(get_db)`) every route uses to get a
    database session. Opens a fresh session per request and closes it
    automatically when the request finishes (the `async with` block) --
    a route function never has to remember to close anything itself.
    """
    async with AsyncSessionLocal() as session:
        yield session
