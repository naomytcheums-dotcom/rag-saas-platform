"""
Partie 2.2.1, items 2/3's own literal task -- uploading and processing a
real batch of already-content-validated files. UNLIKE every prior
bulk-import fan-out in this codebase (one Celery task PER item), this
step's own literal spec lists a SINGLE `process_upload_batch_task` for
the whole batch -- each real file's own S3 upload + Document creation
happens in a real loop inside this ONE task's own execution
(`api/security/documents.py`'s `process_upload_batch`), not fanned out
to a further, separate per-file task.

Each real file's own bytes travel through this task's OWN Celery
arguments, base64-encoded (decoded back to real bytes here before
`process_upload_batch` ever sees them) -- a real, deliberate, DOCUMENTED
exception to this codebase's usual "never smuggle a large blob through
Celery arguments" rule, see `api/security/documents.py`'s
`schedule_upload_batch_processing` for why.
"""

import asyncio
import base64
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import process_upload_batch
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _process_upload_batch_async(
    organization_id: str, workspace_id: str | None, created_by: str | None, file_infos: list[dict],
) -> int:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            files = [
                {"filename": info["filename"], "content_type": info["content_type"], "content": base64.b64decode(info["content_b64"])}
                for info in file_infos
            ]
            scheduled = await process_upload_batch(
                db, uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
                uuid.UUID(created_by) if created_by else None, files,
            )
            await db.commit()
            return scheduled
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.document_batch_processing.process_upload_batch_task")
def process_upload_batch_task(organization_id: str, workspace_id: str | None, created_by: str | None, file_infos: list[dict]) -> int:
    """Item 3's literal task -- traite le lot (voir
    api/security/documents.py's process_upload_batch for the real
    logic, and this module's own docstring for why real bytes travel
    through this task's own arguments, base64-encoded)."""
    return asyncio.run(_process_upload_batch_async(organization_id, workspace_id, created_by, file_infos))
