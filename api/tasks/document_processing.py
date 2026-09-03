"""
Partie 2.1.1, item 4 -- the real async document-processing task, run by
Celery workers. Same asyncio.run() bridge as api/tasks/
domain_verification.py / ssl_certificate_renewal.py, and for the
identical reason: the real work (PDF extraction, chunking, embedding
generation -- api/security/documents.py's process_pdf_document) stays
async for the FastAPI routes/tests that also call it, so duplicating it
as a parallel sync implementation just for this one task would be
needless, error-prone duplication.
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import process_pdf_document
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _process_document_async(document_id: str) -> str:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                document = await process_pdf_document(db, uuid.UUID(document_id))
                await db.commit()
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
