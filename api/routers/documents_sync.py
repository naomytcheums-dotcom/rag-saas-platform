"""
Synchronous document reindex endpoint -- no Celery worker required.

Real, additive: this calls the underlying async reindex function
DIRECTLY (same real `process_document` pipeline every format already
uses) instead of going through Celery's `.delay()` or `.apply()`.

Why not `.apply()`: Celery tasks wrapped with `asyncio.run()` conflict
with FastAPI's own running event loop. This wrapper awaits the async
function directly, staying inside the same loop.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.tasks.reindex import _reindex_document_async

router = APIRouter(tags=["documents-sync"])


@router.post("/documents/{document_id}/reindex-sync")
async def reindex_document_sync(document_id: str, db: AsyncSession = Depends(get_db)):
    """Synchronous reindex -- runs the real pipeline NOW, in this request.

    No Celery worker needed. Returns when the document is fully
    processed (or failed).
    """
    try:
        result = await _reindex_document_async(document_id, None)
        return {"status": "completed", "document_id": document_id, "result": str(result)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
