"""Fire-and-forget document reindex -- no Celery worker needed.

Same permission as `POST /documents/{document_id}/reindex` (api/routers/documents.py): the caller must belong to the document's
organization and be its uploader or an Admin/Owner. This route used to take ANY document id from an anonymous caller and start
a (costly: re-chunking + re-embedding) background reindex of it, across tenants."""

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_current_user, get_db
from api.models.user import User
from api.routers.documents import _get_document_and_membership, _require_document_owner_or_admin
from api.security.rate_limit import enforce_rate_limit
from api.tasks.reindex import _reindex_document_async

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents-sync"])

# asyncio only keeps a weak reference to a task: without this set a fire-and-forget task can be garbage-collected mid-run.
_running: set[asyncio.Task] = set()


async def _run_reindex_safe(document_id: str) -> None:
    try:
        await _reindex_document_async(document_id, None)
        logger.info("reindex-sync completed for %s", document_id)
    except Exception as exc:
        logger.warning("reindex-sync failed for %s: %s", document_id, exc)


@router.post("/documents/{document_id}/reindex-sync", status_code=status.HTTP_202_ACCEPTED)
async def reindex_document_sync(
    document_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    document, membership = await _get_document_and_membership(db, document_id, current_user)
    _require_document_owner_or_admin(document, membership, current_user, "You can only reindex a document you uploaded yourself")
    await enforce_rate_limit(
        f"ratelimit:reindex-sync:org:{document.organization_id}", settings.DOCUMENT_UPLOAD_RATE_LIMIT_MAX_ATTEMPTS, settings.DOCUMENT_UPLOAD_RATE_LIMIT_WINDOW_SECONDS,
    )
    task = asyncio.create_task(_run_reindex_safe(str(document.id)))
    _running.add(task)
    task.add_done_callback(_running.discard)
    return {"status": "started", "document_id": str(document.id)}
