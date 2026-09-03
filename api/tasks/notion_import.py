"""
Partie 2.1.16, items 4/5's own literal tasks -- importing a Notion page
(or a real database's own real pages) and running each through the
shared document pipeline. Same `asyncio.run()` bridge as every other
real task in this codebase.

Neither of this step's own literal task signatures includes a token
argument at all -- matching this codebase's own established
"never thread a real secret through Celery" security answer from the
start (the same real design Partie 2.1.14/2.1.15's own literal task
signatures already had, unlike Partie 2.1.12's own literal
`process_github_repo_task`, which needed correcting).

**`process_notion_page_task` needs its OWN engine/session, and does
BOTH create-the-Document and fetch/process it in one real function**
(api/security/documents.py's import_and_process_notion_page) -- the
SAME real shape as every other per-item task in this codebase.

**`process_notion_database_task` needs no database session at all**
-- api/security/documents.py's process_notion_database only ever
touches real HTTP (Notion's API) and real Celery (dispatching one real
process_notion_page_task per real page, the SAME task the
single-page path uses), never this server's own database directly.
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.documents import import_and_process_notion_page, process_notion_database
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _import_and_process_notion_page_async(page_id: str, organization_id: str, workspace_id: str | None, created_by: str | None) -> str:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                document = await import_and_process_notion_page(
                    db, uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None,
                    uuid.UUID(created_by) if created_by else None, page_id,
                )
                await db.commit()
                return document.status
            except ValueError as exc:
                # Same reasoning as every other per-item task in this
                # codebase -- one bad page (or workspace, or a real,
                # invalid token) must never be treated as a Celery task
                # failure among possibly many siblings in a real batch.
                logger.warning("process_notion_page_task: rejected Notion page '%s': %s", page_id, exc)
                await db.rollback()
                return "rejected"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.notion_import.process_notion_page_task")
def process_notion_page_task(page_id: str, organization_id: str, workspace_id: str | None, created_by: str | None) -> str:
    """Item 5's literal task -- import d'une page Notion, réutilisant
    le pipeline partagé (voir api/security/documents.py's
    import_and_process_notion_page)."""
    return asyncio.run(_import_and_process_notion_page_async(page_id, organization_id, workspace_id, created_by))


@celery_app.task(name="api.tasks.notion_import.process_notion_database_task")
def process_notion_database_task(database_id: str, organization_id: str, workspace_id: str | None, max_pages: int, created_by: str) -> str:
    """Item 5's literal task -- interroge la vraie base Notion, filtre,
    dispatch (see api/security/documents.py's process_notion_database
    for the real logic, and this module's own docstring for why this
    bridge needs no database session)."""
    return asyncio.run(process_notion_database(
        uuid.UUID(organization_id), uuid.UUID(workspace_id) if workspace_id else None, database_id, max_pages, uuid.UUID(created_by),
    ))
