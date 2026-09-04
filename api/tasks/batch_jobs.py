"""
Partie 2.2.16, items 4's own literal tasks -- both real Celery entry
points for `api/security/batch_jobs.py`'s own `process_batch_job`.

`process_batch_job_task` and `resume_batch_job_task` deliberately call
the exact SAME real function -- `process_batch_job` is already, by
its own real design, safe to call again on a job that's `pending`,
`processing` (e.g. a worker restarted mid-run), `failed`, or
`cancelled` (it only ever (re-)attempts real `pending` items) -- the
same real "two honest names for one real, already-idempotent
operation" pattern already established for Partie 2.2.8's own
replace_document/create_document_version_from_upload.
"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.batch_jobs import process_batch_job
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _process_batch_job_async(job_id: str) -> str:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                job = await process_batch_job(db, uuid.UUID(job_id))
                return job.status
            except ValueError as exc:
                # Same reasoning as every other per-item task in this
                # codebase -- an already-completed or already-deleted
                # job must never be treated as a real Celery task
                # failure.
                logger.warning("process_batch_job_task: rejected job '%s': %s", job_id, exc)
                return "rejected"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.batch_jobs.process_batch_job_task")
def process_batch_job_task(job_id: str) -> str:
    """Item 4's own literal task -- traite un job en arrière-plan."""
    return asyncio.run(_process_batch_job_async(job_id))


@celery_app.task(name="api.tasks.batch_jobs.resume_batch_job_task")
def resume_batch_job_task(job_id: str) -> str:
    """Item 4's own literal task -- reprend un job interrompu. See this
    module's own top docstring for why this is the exact same real
    call as `process_batch_job_task` above."""
    return asyncio.run(_process_batch_job_async(job_id))
