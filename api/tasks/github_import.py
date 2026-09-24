"""
Partie 2.1.12/2.1.13's own literal tasks -- fetching a GitHub
repository's real file tree (2.1.12) or real issues (2.1.13) and
fanning real per-item imports out to Celery. Same `asyncio.run()`
bridge as every other real task in this codebase
(api/tasks/document_processing.py, api/tasks/url_import.py,
api/tasks/sitemap_import.py), for the identical reason: the real work
stays async for the FastAPI routes/tests that also call it directly.

**`process_github_repo_task`/`process_github_issues_task` both need no
database session at all**, the SAME real simplification
api/tasks/sitemap_import.py's own process_sitemap_task already has --
their own real logic (api/security/documents.py's process_github_repo/
process_github_issues) only ever touches real HTTP (GitHub's API) and
real Celery (dispatching per-item tasks), never this server's own
database directly.

**`process_github_file_task` needs its OWN engine/session, and does
BOTH create-the-Document and fetch/process-it in one real function**
(api/security/documents.py's import_and_process_github_file) -- see
that function's own docstring for why this is a deliberate
architectural difference from Partie 2.1.10/2.1.11's own per-item
functions, not an inconsistency.

**`process_github_issue_task` ALSO needs its own engine/session, for
the same "create + process in one function" reason, but makes NO
further real GitHub API call at all** -- unlike a file's real content
(fetched INSIDE process_github_file_task, too large to usefully thread
through a Celery argument), one real issue's own JSON plus its real
comments is already small enough, and already fully assembled by
process_github_issues, to travel as this task's own literal `issue_data`
argument directly.
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import (
    import_and_process_github_file,
    import_and_process_github_issue,
    process_github_issues,
    process_github_repo,
)
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


async def _import_and_process_github_file_async(
    file_url: str, organization_id: str, workspace_id: str | None, created_by: str | None,
) -> str:
    engine = make_async_engine()
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


async def _import_and_process_github_issue_async(
    issue_data: dict, organization_id: str, workspace_id: str | None, created_by: str | None,
) -> str:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                document = await import_and_process_github_issue(
                    db, uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
                    uuid.UUID(created_by) if created_by else None, issue_data,
                )
                await db.commit()
                return document.status
            except ValueError as exc:
                # Same reasoning as process_github_file_task -- one bad
                # issue (or workspace) must never be treated as a Celery
                # task failure among possibly hundreds of siblings.
                logger.warning(
                    "process_github_issue_task: rejected issue #%s: %s", issue_data.get("issue", {}).get("number"), exc,
                )
                await db.rollback()
                return "rejected"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.github_import.process_github_issue_task")
def process_github_issue_task(issue_data: dict, organization_id: str, workspace_id: str | None, created_by: str | None) -> str:
    """Item 5's literal task -- import d'une issue (déjà formatée en
    document), réutilisant le pipeline partagé (voir
    api/security/documents.py's import_and_process_github_issue)."""
    return asyncio.run(_import_and_process_github_issue_async(issue_data, organization_id, workspace_id, created_by))


@celery_app.task(name="api.tasks.github_import.process_github_issues_task")
def process_github_issues_task(
    repo_url: str, organization_id: str, workspace_id: str | None,
    state: str, since: str | None, labels: list[str] | None, max_issues: int, created_by: str,
) -> str:
    """Item 4's literal task -- récupère les issues réelles (état/since/
    labels), filtre, dispatch (see api/security/documents.py's
    process_github_issues for the real logic, and this module's own
    docstring for why this bridge needs no database session)."""
    return asyncio.run(process_github_issues(
        uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
        repo_url, state, since, labels, max_issues, uuid.UUID(created_by),
    ))
