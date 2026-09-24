"""
Partie 2.2.13, item 4's own literal periodic task -- checks every real,
non-deleted document that HAS a real `source_url` (see
api/security/documents.py's own get_file_modified_time docstring for
the honest scope of what that covers) for a real source-side
modification, system-wide across every organization -- the same real
"one item's own failure never blocks the rest" resilience as every
other bulk sweep in this codebase.

Runs on Celery Beat's own daily schedule (api/tasks/celery_app.py),
same low-traffic-window convention as every other daily sweep already
registered there -- idempotent by construction: re-running it twice in
a row just re-checks and finds nothing new the second time, never
double-counts or corrupts state.
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.document import Document
from api.security.documents import check_document_modified, mark_document_checked
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


async def _check_modified_documents_async() -> dict:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    checked = 0
    modified = 0
    try:
        async with session_factory() as db:
            document_ids = (await db.scalars(
                select(Document.id).where(Document.source_url.is_not(None), Document.deleted_at.is_(None))
            )).all()
            for document_id in document_ids:
                try:
                    document = await db.get(Document, document_id)
                    if document is None:
                        continue
                    if await check_document_modified(document):
                        modified += 1
                    mark_document_checked(document)
                    # Committed per-document, not once at the very end --
                    # a real failure on document N must roll back ONLY
                    # document N's own partial change, never undo every
                    # OTHER document already successfully checked earlier
                    # in this same sweep.
                    await db.commit()
                    checked += 1
                except Exception as exc:  # noqa: BLE001 -- one document's own real failure must never abort the whole sweep
                    logger.warning("check_modified_documents_task: could not check document '%s': %s", document_id, exc)
                    await db.rollback()
    finally:
        await engine.dispose()
    return {"checked": checked, "modified": modified}


@celery_app.task(name="api.tasks.document_modification_check.check_modified_documents_task")
def check_modified_documents_task() -> dict:
    """Item 4's own literal task name."""
    return asyncio.run(_check_modified_documents_async())
