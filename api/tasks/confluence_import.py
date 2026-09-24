"""
Partie 2.1.17, items 4/5's own literal tasks -- importing a Confluence
page (or a real space's own real pages) and running each through the
shared document pipeline. Same `asyncio.run()` bridge as every other
real task in this codebase. Neither of this step's own literal task
signatures needs a token argument in this codebase's own design --
CONFLUENCE_API_TOKEN/CONFLUENCE_BASE_URL are read fresh from settings
inside whichever function actually needs them, the same security
answer every prior real API token in this codebase already has.

**`process_confluence_page_task` needs its OWN engine/session, and
does BOTH create-the-Document and fetch/process it in one real
function** (api/security/documents.py's import_and_process_confluence_page)
-- the SAME real shape as every other per-item task in this codebase.

**`process_confluence_space_task` needs no database session at all**
-- api/security/documents.py's process_confluence_space only ever
touches real HTTP (Confluence's API) and real Celery (dispatching one
real process_confluence_page_task per real page, the SAME task the
single-page path uses), never this server's own database directly.
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import import_and_process_confluence_page, process_confluence_space
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


async def _import_and_process_confluence_page_async(page_id: str, organization_id: str, workspace_id: str | None, created_by: str | None) -> str:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                document = await import_and_process_confluence_page(
                    db, uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
                    uuid.UUID(created_by) if created_by else None, page_id,
                )
                await db.commit()
                return document.status
            except ValueError as exc:
                logger.warning("process_confluence_page_task: rejected Confluence page '%s': %s", page_id, exc)
                await db.rollback()
                return "rejected"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.confluence_import.process_confluence_page_task")
def process_confluence_page_task(page_id: str, organization_id: str, workspace_id: str | None, created_by: str | None) -> str:
    """Item 5's literal task -- import d'une page Confluence,
    réutilisant le pipeline partagé (voir api/security/documents.py's
    import_and_process_confluence_page)."""
    return asyncio.run(_import_and_process_confluence_page_async(page_id, organization_id, workspace_id, created_by))


@celery_app.task(name="api.tasks.confluence_import.process_confluence_space_task")
def process_confluence_space_task(space_key: str, organization_id: str, workspace_id: str | None, max_pages: int, created_by: str) -> str:
    """Item 5's literal task -- récupère les vraies pages de l'espace,
    filtre, dispatch (see api/security/documents.py's
    process_confluence_space for the real logic, and this module's own
    docstring for why this bridge needs no database session)."""
    return asyncio.run(process_confluence_space(
        uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None, space_key, max_pages, uuid.UUID(created_by),
    ))
