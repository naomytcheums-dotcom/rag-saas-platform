"""Fire-and-forget document reindex -- no Celery worker needed."""

import asyncio
import logging

from fastapi import APIRouter, status

from api.tasks.reindex import _reindex_document_async

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents-sync"])


async def _run_reindex_safe(document_id: str) -> None:
    try:
        await _reindex_document_async(document_id, None)
        logger.info("reindex-sync completed for %s", document_id)
    except Exception as exc:
        logger.warning("reindex-sync failed for %s: %s", document_id, exc)


@router.post("/documents/{document_id}/reindex-sync", status_code=status.HTTP_202_ACCEPTED)
async def reindex_document_sync(document_id: str):
    asyncio.create_task(_run_reindex_safe(document_id))
    return {"status": "started", "document_id": document_id}
