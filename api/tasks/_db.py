"""Real fix (2026-09-24): shared DB helpers for Celery tasks.

The Celery worker with --concurrency=16 creates one async engine per
task execution. Each engine's own pool (default: pool_size=5,
max_overflow=10) can reach 80 connections total -- but Supabase's
session-mode pooler (port 5432) caps at 15 connections TOTAL.

This module centralizes two things:
1. The TRANSACTION-mode URL (port 6543, supports 200+ connections)
2. The asyncpg connect_args required by that mode (no prepared statements)

Every task file imports from here instead of duplicating the logic.
"""

from api.config import settings


def transaction_url() -> str:
    """Prefer Supabase's TRANSACTION-mode pooler (port 6543)."""
    return settings.DATABASE_URL_TRANSACTION or settings.DATABASE_URL


def transaction_connect_args() -> dict:
    """asyncpg caches must be disabled in transaction mode."""
    if settings.DATABASE_URL_TRANSACTION:
        return {"statement_cache_size": 0, "prepared_statement_cache_size": 0}
    return {}


def make_async_engine():
    """Create a properly-configured async engine for a Celery task."""
    from sqlalchemy.ext.asyncio import create_async_engine

    return create_async_engine(
        transaction_url(),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
        connect_args=transaction_connect_args(),
    )
