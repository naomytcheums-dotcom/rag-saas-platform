"""
Synchronous document reindex endpoint -- no Celery worker required.

Real, additive: this is a thin wrapper around the existing
`reindex_document_task` (api/tasks/reindex.py) that calls it
SYNCHRONOUSLY via `.apply()` instead of `.delay()`. This lets a
deployment without a running Celery worker still process documents
on demand (e.g. Render free tier, hackathon demo).

The underlying task is UNCHANGED -- same real `process_document`
pipeline every format already uses. Only the dispatch mode differs.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.tasks.reindex import reindex_document_task

router = APIRouter(tags=["documents-sync"])


@router.post("/documents/{document_id}/reindex-sync")
async def reindex_document_sync(document_id: str, db: AsyncSession = Depends(get_db)):
    """Synchronous reindex -- runs the real pipeline NOW, in this request.

    No Celery worker needed. Returns when the document is fully
    processed (or failed).
    """
    try:
        result = reindex_document_task.apply(args=[document_id, None])
        if result.failed():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Reindex failed: {result.result}",
            )
        return {"status": "completed", "document_id": document_id, "result": str(result.result)}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
