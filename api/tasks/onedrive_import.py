"""
Partie 2.1.18, items 4/5's own literal tasks -- listing a OneDrive
folder's (or resolving a single OneDrive file's) real files and fanning
real per-file imports out to Celery. Same `asyncio.run()` bridge as
every other real task in this codebase, for the identical reason: the
real work stays async for the FastAPI routes/tests that also call it
directly.

Neither of this step's own literal task signatures includes a token
argument at all -- same "already reflects the real never-thread-a-
secret-through-Celery answer from the start" shape as Partie 2.1.14's
own `process_google_drive_task`/`process_google_drive_file_task`.
Every real Graph API call instead reads `settings.ONEDRIVE_REFRESH_TOKEN`
fresh and calls `authenticate_onedrive` itself, inside whichever
function actually needs a real access token
(api/security/documents.py's process_onedrive/import_and_process_onedrive_file).

**`process_onedrive_task` needs no database session at all**, the SAME
real simplification `process_google_drive_task` already has.

**`process_onedrive_file_task` needs its OWN engine/session, and makes
its OWN real `authenticate_onedrive` call** -- see
`import_and_process_onedrive_file`'s own docstring for why this task
does NOT reuse an access token obtained earlier by `process_onedrive`.
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import import_and_process_onedrive_file, process_onedrive
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


async def _import_and_process_onedrive_file_async(
    file_id: str, organization_id: str, workspace_id: str | None, created_by: str | None,
) -> str:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                document = await import_and_process_onedrive_file(
                    db, uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
                    uuid.UUID(created_by) if created_by else None, file_id,
                )
                await db.commit()
                return document.status
            except ValueError as exc:
                # Same reasoning as process_google_drive_file_task -- one
                # bad file (or workspace, or a real, expired refresh
                # token) must never be treated as a Celery task failure
                # among possibly hundreds of siblings.
                logger.warning("process_onedrive_file_task: rejected OneDrive file '%s': %s", file_id, exc)
                await db.rollback()
                return "rejected"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.onedrive_import.process_onedrive_file_task")
def process_onedrive_file_task(file_id: str, organization_id: str, workspace_id: str | None, created_by: str | None) -> str:
    """Item 5's literal task -- import d'un fichier OneDrive, réutilisant
    le pipeline partagé (voir api/security/documents.py's
    import_and_process_onedrive_file)."""
    return asyncio.run(_import_and_process_onedrive_file_async(file_id, organization_id, workspace_id, created_by))


@celery_app.task(name="api.tasks.onedrive_import.process_onedrive_task")
def process_onedrive_task(
    folder_id: str, organization_id: str, workspace_id: str | None, patterns: list[str] | None, max_files: int, created_by: str,
) -> str:
    """Item 4's literal task -- résout le dossier/fichier OneDrive réel,
    filtre, dispatch (see api/security/documents.py's process_onedrive
    for the real logic, and this module's own docstring for why this
    bridge needs no database session)."""
    return asyncio.run(process_onedrive(
        uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
        folder_id, patterns, max_files, uuid.UUID(created_by),
    ))
