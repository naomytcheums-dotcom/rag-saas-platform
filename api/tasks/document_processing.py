"""
Partie 2.1.1/2.1.2, item 4 -- the real async document-processing task,
run by Celery workers. Same asyncio.run() bridge as api/tasks/
domain_verification.py / ssl_certificate_renewal.py, and for the
identical reason: the real work (PDF/DOCX extraction, chunking,
embedding generation -- api/security/documents.py's process_document)
stays async for the FastAPI routes/tests that also call it, so
duplicating it as a parallel sync implementation just for this one task
would be needless, error-prone duplication. This task's own name was
already format-agnostic from 2.1.1 onward -- only the function it calls
needed renaming once DOCX support made "process_pdf_document" inaccurate.
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import process_document
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


async def _notify_document_outcome(db, document) -> None:
    """Phase 5, Étape 4 -- job_completed/job_failed, the one real
    trigger this étape wires for the "job" domain. `created_by` is
    nullable (a system-imported document has no real uploader to
    notify) -- silently skipped, not an error."""
    if document.created_by is None:
        return
    from api.services.notifications import create_notification

    notification_type = "job_completed" if document.status == "completed" else "job_failed" if document.status == "failed" else None
    if notification_type is None:
        return
    try:
        await create_notification(
            db, organization_id=document.organization_id, user_id=document.created_by, notification_type=notification_type,
            context={"document_name": document.name, "error": (document.metadata_json or {}).get("error")},
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001 -- a notification failure must never fail the real document processing it only reports on
        logger.warning("_notify_document_outcome: could not notify for document '%s': %s", document.id, exc)


async def _process_document_async(document_id: str) -> str:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                document = await process_document(db, uuid.UUID(document_id))
                await db.commit()
                await _notify_document_outcome(db, document)
                return document.status
            except ValueError:
                # The document was deleted between being scheduled and
                # this task actually running -- nothing left to process.
                await db.rollback()
                return "not_found"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.document_processing.process_document_task")
def process_document_task(document_id: str) -> str:
    """
    Item 4's literal task -- dispatched once per upload
    (api/security/documents.py's schedule_document_processing).
    Returns the document's final status string, mainly so a manual
    invocation or test can assert on it.
    """
    return asyncio.run(_process_document_async(document_id))
