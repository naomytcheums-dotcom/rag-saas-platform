"""
Partie 2.1.10, item 4's own "asynchrone via Celery" answer (vision
critique Q4) -- the real fetch-and-process task, run by Celery workers.
Same asyncio.run() bridge as api/tasks/document_processing.py and
api/tasks/domain_verification.py/ssl_certificate_renewal.py, for the
identical reason: the real work (fetch/validate a URL, then the
existing process_document pipeline -- api/security/documents.py's
process_url_document) stays async for the FastAPI routes/tests that
also call it.
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import process_url_document
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


async def _fetch_and_process_url_async(document_id: str) -> str:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                document = await process_url_document(db, uuid.UUID(document_id))
                await db.commit()
                return document.status
            except ValueError:
                # The document was deleted between being scheduled and
                # this task actually running -- nothing left to import.
                await db.rollback()
                return "not_found"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.url_import.fetch_and_process_url_task")
def fetch_and_process_url_task(document_id: str) -> str:
    """
    Item 1/3's literal task -- dispatched once per URL import
    (api/security/documents.py's schedule_url_import). Returns the
    document's final status string, mainly so a manual invocation or
    test can assert on it.
    """
    return asyncio.run(_fetch_and_process_url_async(document_id))
