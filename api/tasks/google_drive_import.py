"""
Partie 2.1.14, items 4/5's own literal tasks -- listing a Google Drive
folder's (or resolving a single Drive file's) real files and fanning
real per-file imports out to Celery. Same `asyncio.run()` bridge as
every other real task in this codebase (api/tasks/document_processing.py,
api/tasks/url_import.py, api/tasks/sitemap_import.py,
api/tasks/github_import.py), for the identical reason: the real work
stays async for the FastAPI routes/tests that also call it directly.

Neither of this step's own literal task signatures includes a token
argument at all -- unlike Partie 2.1.12's own literal
`process_github_repo_task` (which DID list one, deliberately dropped by
api/security/documents.py) -- so there is nothing to correct here: this
step's own spec already reflects the real "never thread a secret
through Celery" security answer from the start. Every real Drive API
call instead reads `settings.GOOGLE_DRIVE_REFRESH_TOKEN` fresh and
calls `authenticate_drive` itself, inside whichever function actually
needs a real access token (api/security/documents.py's
process_google_drive/import_and_process_google_drive_file).

**`process_google_drive_task` needs no database session at all**, the
SAME real simplification `process_sitemap_task`/`process_github_repo_task`/
`process_github_issues_task` already have -- `process_google_drive`
only ever touches real HTTP (Drive's/Google's OAuth API) and real
Celery (dispatching per-file tasks), never this server's own database
directly.

**`process_google_drive_file_task` needs its OWN engine/session, and
makes its OWN real `authenticate_drive` call** -- see
`import_and_process_google_drive_file`'s own docstring for why this
task does NOT reuse an access token obtained earlier by
`process_google_drive` (a real access token can genuinely expire
between when a large batch is fanned out and when a later task in that
same batch actually runs; each task gets its own real, freshly-checked
one instead of risking a stale one).
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import import_and_process_google_drive_file, process_google_drive
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


async def _import_and_process_google_drive_file_async(
    file_id: str, organization_id: str, workspace_id: str | None, created_by: str | None,
) -> str:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                document = await import_and_process_google_drive_file(
                    db, uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
                    uuid.UUID(created_by) if created_by else None, file_id,
                )
                await db.commit()
                return document.status
            except ValueError as exc:
                # Same reasoning as process_github_file_task -- one bad
                # file (or workspace, or a real, expired refresh token)
                # must never be treated as a Celery task failure among
                # possibly hundreds of siblings.
                logger.warning("process_google_drive_file_task: rejected Drive file '%s': %s", file_id, exc)
                await db.rollback()
                return "rejected"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.google_drive_import.process_google_drive_file_task")
def process_google_drive_file_task(file_id: str, organization_id: str, workspace_id: str | None, created_by: str | None) -> str:
    """Item 5's literal task -- import d'un fichier Drive, réutilisant
    le pipeline partagé (voir api/security/documents.py's
    import_and_process_google_drive_file)."""
    return asyncio.run(_import_and_process_google_drive_file_async(file_id, organization_id, workspace_id, created_by))


@celery_app.task(name="api.tasks.google_drive_import.process_google_drive_task")
def process_google_drive_task(
    drive_id: str, organization_id: str, workspace_id: str | None, patterns: list[str] | None, max_files: int, created_by: str,
) -> str:
    """Item 4's literal task -- résout le dossier/fichier Drive réel,
    filtre, dispatch (see api/security/documents.py's process_google_drive
    for the real logic, and this module's own docstring for why this
    bridge needs no database session)."""
    return asyncio.run(process_google_drive(
        uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
        drive_id, patterns, max_files, uuid.UUID(created_by),
    ))
