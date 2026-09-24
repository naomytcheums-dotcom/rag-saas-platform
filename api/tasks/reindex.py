"""
Partie 2.2.9, items 2/3's own literal tasks -- manually re-triggering a
real document's own extraction/chunking/embedding pipeline (a single
document, or every real, non-deleted document in an organization).

Neither task does any NEW real work of its own: `reindex_document_task`
bridges to `process_document` (the SAME real pipeline every format has
used since Partie 2.1.1, which already deletes and recreates a
document's own chunks on any rerun), and
`reindex_organization_documents_task` bridges to `reindex_organization`,
which fans out to real, individual `reindex_document_task` calls (one
real Celery task per real document, the SAME resilience shape as every
other bulk operation in this codebase -- one document's own real
failure never blocks the rest).

`triggered_by` -- a real, small, optional parameter added on both
tasks by Partie 2.2.10, not in this step's own original literal
signature -- carries the real, honest actor a `document_audit_logs`
"reindexed" entry gets attributed to; `None` for a real reindex with no
known human trigger (e.g. a future scheduled/automatic reindex),
never a fabricated one.
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import reindex_document, reindex_organization
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


async def _reindex_document_async(document_id: str, triggered_by: str | None) -> str:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                status_value = await reindex_document(db, uuid.UUID(document_id), uuid.UUID(triggered_by) if triggered_by else None)
                await db.commit()
                return status_value
            except ValueError as exc:
                # Same reasoning as every other per-item task in this
                # codebase -- one bad (or already-deleted) document
                # must never be treated as a Celery task failure among
                # possibly hundreds of siblings in an org-wide reindex.
                logger.warning("reindex_document_task: rejected document '%s': %s", document_id, exc)
                await db.rollback()
                return "rejected"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.reindex.reindex_document_task")
def reindex_document_task(document_id: str, triggered_by: str | None = None) -> str:
    """Item 2's own literal task -- réindexe un seul document (voir
    api/security/documents.py's reindex_document for the real logic --
    it's the exact same real process_document pipeline every format
    already uses, not new extraction/chunking code)."""
    return asyncio.run(_reindex_document_async(document_id, triggered_by))


async def _reindex_organization_documents_async(organization_id: str, triggered_by: str | None) -> int:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            return await reindex_organization(db, uuid.UUID(organization_id), uuid.UUID(triggered_by) if triggered_by else None)
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.reindex.reindex_organization_documents_task")
def reindex_organization_documents_task(organization_id: str, triggered_by: str | None = None) -> int:
    """Item 2's own literal task -- liste et dispatch un vrai
    reindex_document_task par document réel et non supprimé de
    l'organisation (voir api/security/documents.py's
    reindex_organization for the real fan-out logic)."""
    return asyncio.run(_reindex_organization_documents_async(organization_id, triggered_by))
