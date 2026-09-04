"""
Partie 2.1.19, items 4/5's own literal tasks -- importing a real,
already-uploaded ZIP archive's own surviving entries. The ONLY import
source in this whole 2.1.10-2.1.19 series needing NO real external
API/credential of any kind -- purely local, stdlib `zipfile` work
against a file this server already has in its own S3 bucket (the SAME
upload route/bucket every other format already uses, Partie 2.1.1).

`process_zip_task` needs a real database session (unlike
process_google_drive_task/process_confluence_space_task's own "no
database needed" shape, since those reach a real external API directly)
-- looking the already-uploaded zip Document up by id and downloading
its real bytes from S3 both need one; see
api/security/documents.py's import_and_process_zip_archive for the
real logic.

`process_zip_entry_task` needs its OWN engine/session too, and makes
its OWN real, fresh download of the container archive from S3 -- see
api/security/documents.py's import_and_process_zip_entry (and
process_zip_entries' own docstring) for why a real local temp file path
from process_zip_task's own run is never assumed to still be valid
here (a real, distributed, multi-worker Celery deployment offers no
such guarantee).

Neither of this step's own literal task signatures listed `created_by`
-- added anyway here, the SAME "honest provenance" deviation already
established from Partie 2.1.11 onward (avoiding a real
Document.created_by = None for a document a real user's own request
actually triggered).
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import import_and_process_zip_archive, import_and_process_zip_entry
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _import_and_process_zip_entry_async(
    entry_data: dict, organization_id: str, workspace_id: str | None, created_by: str | None,
) -> str:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                document = await import_and_process_zip_entry(
                    db, uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
                    uuid.UUID(created_by) if created_by else None,
                    uuid.UUID(entry_data["zip_file_id"]), entry_data["entry_name"],
                )
                await db.commit()
                return document.status
            except ValueError as exc:
                # Same reasoning as process_google_drive_file_task -- one
                # bad entry (or workspace, or a real, no-longer-existing
                # zip Document) must never be treated as a Celery task
                # failure among possibly hundreds of siblings.
                logger.warning("process_zip_entry_task: rejected zip entry '%s': %s", entry_data.get("entry_name"), exc)
                await db.rollback()
                return "rejected"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.zip_import.process_zip_entry_task")
def process_zip_entry_task(entry_data: dict, organization_id: str, workspace_id: str | None, created_by: str | None) -> str:
    """Item 5's literal task -- import d'une entree ZIP, reutilisant le
    pipeline partage (voir api/security/documents.py's
    import_and_process_zip_entry)."""
    return asyncio.run(_import_and_process_zip_entry_async(entry_data, organization_id, workspace_id, created_by))


async def _process_zip_task_async(
    zip_file_id: str, organization_id: str, workspace_id: str | None,
    patterns: list[str] | None, max_files: int, created_by: str | None,
) -> str:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            document = await import_and_process_zip_archive(
                db, uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
                uuid.UUID(created_by) if created_by else None, uuid.UUID(zip_file_id), patterns, max_files,
            )
            await db.commit()
            return document.status
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.zip_import.process_zip_task")
def process_zip_task(
    zip_file_id: str, organization_id: str, workspace_id: str | None,
    patterns: list[str] | None, max_files: int, created_by: str | None,
) -> str:
    """Item 4's literal task -- ouvre l'archive ZIP deja uploadee,
    filtre et dispatch ses entrees reelles (voir
    api/security/documents.py's import_and_process_zip_archive/
    process_zip_archive for the real logic)."""
    return asyncio.run(_process_zip_task_async(zip_file_id, organization_id, workspace_id, patterns, max_files, created_by))
