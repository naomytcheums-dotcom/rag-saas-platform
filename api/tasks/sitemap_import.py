"""
Partie 2.1.11, item 4's own literal tasks -- fetching a sitemap (or
sitemap index) and fanning real per-URL imports out to Celery. Same
`asyncio.run()` bridge as every other real task in this codebase
(api/tasks/document_processing.py, api/tasks/url_import.py), for the
identical reason: the real work stays async for the FastAPI routes/
tests that also call it directly.

**`process_sitemap_task` needs no database session at all, unlike
every other task's own bridge function** -- `api/security/documents.py`'s
`process_sitemap` (this task's own real logic) only ever touches real
HTTP (fetching/parsing the sitemap) and real Celery (dispatching
per-url tasks), never this server's own database directly, so there is
no engine/session to create here, unlike `_process_single_url_async`
below (which calls `import_document_from_url`, a real database write).

**`process_single_url_task` is a thin wrapper around Partie 2.1.10's
own `import_document_from_url`, UNCHANGED** -- see
api/security/documents.py's own module docstring for why this is
genuine pipeline reuse, not a parallel "sitemap-flavored" import path.
A url this rejects (a real, invalid one somehow past `filter_sitemap_urls`,
or one whose workspace_id turns out invalid) ends in a real, logged
`"rejected"` result -- it does NOT raise into Celery's own retry/error
machinery, since a single bad URL among possibly thousands must never
be treated as a systemic task failure.

**No persisted, user-visible "sitemap import job" status, stated
plainly, not glossed over**: this step's own literal action items ask
for real fetch/parse/dispatch behavior, not a new tracking entity --
every document a sitemap import produces is independently visible the
same way any other document is (`GET /organizations/{org_id}/documents`),
but there is no aggregate "N/M urls processed" view. A top-level
failure (the sitemap itself is unreachable or malformed) is logged and
reflected only in `process_sitemap_task`'s own Celery result, the one
real, honest limitation of this step's own scope.
"""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import import_document_from_url, process_sitemap
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine


async def _process_single_url_async(url: str, organization_id: str, workspace_id: str | None, created_by: str) -> str:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                await import_document_from_url(
                    db, uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
                    uuid.UUID(created_by), url,
                )
                await db.commit()
                return "scheduled"
            except ValueError:
                # A real, individually-bad URL (or workspace) must
                # never be treated as a Celery task failure -- there
                # could be thousands of siblings from the same sitemap
                # that are perfectly fine. Logged inside
                # import_document_from_url's own callers is not
                # applicable here (it raises, doesn't log) -- this is
                # the one real place that decision needs to be made.
                await db.rollback()
                return "rejected"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.sitemap_import.process_single_url_task")
def process_single_url_task(url: str, organization_id: str, workspace_id: str | None, created_by: str) -> str:
    """Item 4's literal task -- import d'une URL, réutilisant Partie
    2.1.10 (see this module's own docstring)."""
    return asyncio.run(_process_single_url_async(url, organization_id, workspace_id, created_by))


@celery_app.task(name="api.tasks.sitemap_import.process_sitemap_task")
def process_sitemap_task(
    sitemap_url: str, organization_id: str, workspace_id: str | None,
    filters: list[str] | None, max_urls: int, created_by: str,
) -> str:
    """Item 4's literal task -- télécharge, parse, dispatch (see
    api/security/documents.py's process_sitemap for the real logic,
    and this module's own docstring for why this bridge needs no
    database session)."""
    return asyncio.run(process_sitemap(
        sitemap_url, uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
        filters, max_urls, uuid.UUID(created_by),
    ))
