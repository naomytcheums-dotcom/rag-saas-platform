"""
Partie 2.1.12, items 4/5's own literal tasks -- fetching a GitHub
repository's real file tree and fanning real per-file imports out to
Celery. Same `asyncio.run()` bridge as every other real task in this
codebase (api/tasks/document_processing.py, api/tasks/url_import.py,
api/tasks/sitemap_import.py), for the identical reason: the real work
stays async for the FastAPI routes/tests that also call it directly.

**`process_github_repo_task` needs no database session at all**, the
SAME real simplification api/tasks/sitemap_import.py's own
process_sitemap_task already has -- api/security/documents.py's
process_github_repo (this task's own real logic) only ever touches
real HTTP (GitHub's API) and real Celery (dispatching per-file tasks),
never this server's own database directly.

**`process_github_file_task` needs its OWN engine/session, and does
BOTH create-the-Document and fetch/process-it in one real function**
(api/security/documents.py's import_and_process_github_file) -- see
that function's own docstring for why this is a deliberate
architectural difference from Partie 2.1.10/2.1.11's own per-item
functions, not an inconsistency.
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import import_and_process_github_file, process_github_repo
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _import_and_process_github_file_async(
    file_url: str, organization_id: str, workspace_id: str | None, created_by: str | None,
) -> str:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                document = await import_and_process_github_file(
                    db, uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
                    uuid.UUID(created_by) if created_by else None, file_url,
                )
                await db.commit()
                return document.status
            except ValueError as exc:
                # A real, individually-bad file url (or workspace) must
                # never be treated as a Celery task failure -- there
                # could be hundreds of siblings from the same repo that
                # are perfectly fine. Same reasoning as Partie 2.1.11's
                # own process_single_url_task.
                logger.warning("process_github_file_task: rejected '%s': %s", file_url, exc)
                await db.rollback()
                return "rejected"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.github_import.process_github_file_task")
def process_github_file_task(file_url: str, organization_id: str, workspace_id: str | None, created_by: str | None) -> str:
    """Item 5's literal task -- import d'un fichier, réutilisant le
    pipeline partagé (voir api/security/documents.py's
    import_and_process_github_file)."""
    return asyncio.run(_import_and_process_github_file_async(file_url, organization_id, workspace_id, created_by))


@celery_app.task(name="api.tasks.github_import.process_github_repo_task")
def process_github_repo_task(
    repo_url: str, organization_id: str, workspace_id: str | None,
    file_patterns: list[str] | None, max_files: int, created_by: str,
) -> str:
    """Item 4's literal task -- télécharge la liste réelle des fichiers,
    filtre, dispatch (see api/security/documents.py's process_github_repo
    for the real logic, and this module's own docstring for why this
    bridge needs no database session)."""
    return asyncio.run(process_github_repo(
        uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
        repo_url, file_patterns, max_files, uuid.UUID(created_by),
    ))
