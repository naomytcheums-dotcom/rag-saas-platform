"""
Partie 2.1.15, items 4/5's own literal tasks -- exporting a Google Doc/
Sheet/Slide (or a real batch of them) and running it through the
shared document pipeline. Same `asyncio.run()` bridge as every other
real task in this codebase, for the identical reason: the real work
stays async for the FastAPI routes/tests that also call it directly.

**`process_google_doc_task` needs its OWN engine/session, and does
BOTH create-the-Document and export/process it in one real function**
(api/security/documents.py's import_and_process_google_doc) -- the
SAME real shape as Partie 2.1.14's own process_google_drive_file_task,
and for the identical reason: the real doc_type/export format are only
known once this task's own real metadata fetch actually runs, so there
is no earlier synchronous moment a pending Document could exist at.

**`process_google_docs_batch_task` needs no database session at all**
-- api/security/documents.py's process_google_docs_batch only ever
touches real Celery (dispatching one real process_google_doc_task per
real document id, the SAME task the single-document path uses), never
this server's own database directly.
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import import_and_process_google_doc, process_google_docs_batch
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


async def _import_and_process_google_doc_async(
    document_id: str, organization_id: str, workspace_id: str | None, export_format: str | None, created_by: str | None,
) -> str:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                document = await import_and_process_google_doc(
                    db, uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
                    uuid.UUID(created_by) if created_by else None, document_id, export_format,
                )
                await db.commit()
                return document.status
            except ValueError as exc:
                # Same reasoning as every other per-item task in this
                # codebase -- one bad document (or workspace, or a real,
                # expired refresh token) must never be treated as a
                # Celery task failure among possibly many siblings in a
                # real batch.
                logger.warning("process_google_doc_task: rejected Google Doc '%s': %s", document_id, exc)
                await db.rollback()
                return "rejected"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.google_docs_import.process_google_doc_task")
def process_google_doc_task(
    document_id: str, organization_id: str, workspace_id: str | None, export_format: str | None, created_by: str | None,
) -> str:
    """Item 5's literal task -- import d'un document Google
    Docs/Sheets/Slides, réutilisant le pipeline partagé (voir
    api/security/documents.py's import_and_process_google_doc)."""
    return asyncio.run(_import_and_process_google_doc_async(document_id, organization_id, workspace_id, export_format, created_by))


@celery_app.task(name="api.tasks.google_docs_import.process_google_docs_batch_task")
def process_google_docs_batch_task(document_ids: list[str], organization_id: str, workspace_id: str | None, created_by: str) -> int:
    """Item 5's literal task -- dispatch réel d'un lot de documents,
    un process_google_doc_task réel par id (voir
    api/security/documents.py's process_google_docs_batch for the real
    logic, and this module's own docstring for why this bridge needs
    no database session)."""
    return process_google_docs_batch(
        uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None, document_ids, uuid.UUID(created_by),
    )
