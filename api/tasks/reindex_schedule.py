"""
Partie 2.2.15, items 4/5's own literal tasks -- executing one real,
due `ReindexSchedule` (re-running Partie 2.2.9's own unchanged
`reindex_organization`), and Celery Beat's own periodic checker that
decides WHICH real schedules (and per-document overrides) are due
right now.

Same `asyncio.run()` + per-invocation engine/session bridge as every
other real Celery task in this codebase.
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.reindex_schedules import run_scheduled_reindexes, schedule_reindex
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _execute_scheduled_reindex_async(schedule_id: str) -> int:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                scheduled_count = await schedule_reindex(db, uuid.UUID(schedule_id))
                await db.commit()
                return scheduled_count
            except ValueError as exc:
                # Same reasoning as every other per-item task in this
                # codebase -- an already-deleted schedule must never be
                # treated as a Celery task failure.
                logger.warning("execute_scheduled_reindex_task: rejected schedule '%s': %s", schedule_id, exc)
                await db.rollback()
                return 0
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.reindex_schedule.execute_scheduled_reindex_task")
def execute_scheduled_reindex_task(schedule_id: str) -> int:
    """Item 4's own literal task -- exécute un schedule dû."""
    return asyncio.run(_execute_scheduled_reindex_async(schedule_id))


async def _check_scheduled_reindexes_async() -> dict:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            result = await run_scheduled_reindexes(db)
            await db.commit()
            return result
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.reindex_schedule.check_scheduled_reindexes_task")
def check_scheduled_reindexes_task() -> dict:
    """Item 5's own literal Celery Beat task -- vérifie, système
    entier, chaque schedule d'organisation ET chaque override par
    document, exécute réellement ceux qui sont dus (voir
    api/security/reindex_schedules.py's own run_scheduled_reindexes for
    the real per-item resilience)."""
    return asyncio.run(_check_scheduled_reindexes_async())
