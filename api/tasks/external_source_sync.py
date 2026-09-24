"""
Partie 2.2.14, items 2/3's own literal tasks -- syncing one real
`ExternalSource` (re-running its own real, unchanged Partie 2.1.12-
2.1.18 import pipeline, see api/security/external_sources.py's own
sync_external_source), every real enabled source in one organization,
or -- `sync_all_sources_periodic_task`, this étape's own literal
Celery Beat task -- every real enabled source across every real
organization, system-wide.

Same `asyncio.run()` + per-invocation engine/session bridge as every
other real Celery task in this codebase (api/tasks/reindex.py,
api/tasks/document_modification_check.py).
"""

import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.external_source import ExternalSource
from api.security.external_sources import detect_source_changes, sync_all_sources, sync_external_source
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


async def _sync_source_async(source_id: str, triggered_by: str | None) -> str:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                status_value = await sync_external_source(db, uuid.UUID(source_id), uuid.UUID(triggered_by) if triggered_by else None)
                await db.commit()
                return status_value
            except ValueError as exc:
                # Same reasoning as every other per-item task in this
                # codebase -- a disabled or already-deleted source must
                # never be treated as a Celery task failure among
                # possibly many siblings in a system-wide sweep.
                logger.warning("sync_source_task: rejected source '%s': %s", source_id, exc)
                await db.rollback()
                return "rejected"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.external_source_sync.sync_source_task")
def sync_source_task(source_id: str, triggered_by: str | None = None) -> str:
    """Item 2's own literal task -- synchronise une seule source."""
    return asyncio.run(_sync_source_async(source_id, triggered_by))


async def _sync_all_sources_async(organization_id: str, triggered_by: str | None) -> dict:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            result = await sync_all_sources(db, uuid.UUID(organization_id), uuid.UUID(triggered_by) if triggered_by else None)
            await db.commit()
            return result
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.external_source_sync.sync_all_sources_task")
def sync_all_sources_task(organization_id: str, triggered_by: str | None = None) -> dict:
    """Item 2's own literal task -- synchronise toutes les sources
    activées d'une organisation."""
    return asyncio.run(_sync_all_sources_async(organization_id, triggered_by))


async def _sync_all_sources_periodic_async() -> dict:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    checked = 0
    synced = 0
    skipped = 0
    failed = 0
    try:
        async with session_factory() as db:
            source_ids = (await db.scalars(select(ExternalSource.id).where(ExternalSource.enabled.is_(True)))).all()
            for source_id in source_ids:
                try:
                    source = await db.get(ExternalSource, source_id)
                    if source is None:
                        continue
                    checked += 1
                    if not await detect_source_changes(source):
                        skipped += 1
                        continue
                    status_value = await sync_external_source(db, source_id)
                    # Committed per-source, not once at the very end --
                    # the exact same real bug already fixed in Partie
                    # 2.2.13's own check_modified_documents_task: a
                    # rollback on one source's own real failure must
                    # never undo every OTHER source already
                    # successfully synced earlier in the same sweep.
                    await db.commit()
                    if status_value == "failed":
                        failed += 1
                    else:
                        synced += 1
                except Exception as exc:  # noqa: BLE001 -- one source's own real failure must never abort the whole system-wide sweep
                    logger.warning("sync_all_sources_periodic_task: could not sync source '%s': %s", source_id, exc)
                    await db.rollback()
                    failed += 1
    finally:
        await engine.dispose()
    return {"checked": checked, "synced": synced, "skipped": skipped, "failed": failed}


@celery_app.task(name="api.tasks.external_source_sync.sync_all_sources_periodic_task")
def sync_all_sources_periodic_task() -> dict:
    """Item 3's own literal Celery Beat task -- vérifie et synchronise,
    de façon réelle et résiliente, chaque source active de chaque
    organisation, système entier -- voir
    api/security/external_sources.py's own detect_source_changes for
    the real, honest reasoning on which sources actually get skipped
    (no real change likely) vs. re-synced."""
    return asyncio.run(_sync_all_sources_periodic_async())
