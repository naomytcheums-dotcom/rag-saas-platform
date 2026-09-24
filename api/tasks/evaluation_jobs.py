"""Partie 7.3.1 -- the real Celery entry point for
`api/services/evaluation_jobs.py`'s own `run_evaluation_job`. Same
real, standalone-engine-per-task shape as `api/tasks/batch_jobs.py`
(a Celery worker runs in its own real process, never shares the
FastAPI request's own real DB session)."""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.services.evaluation_jobs import run_evaluation_job
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


async def _run_evaluation_job_async(job_id: str) -> str:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                job = await run_evaluation_job(db, uuid.UUID(job_id))
                return job.status if job is not None else "not_found"
            except ValueError as exc:
                logger.warning("run_evaluation_job_task: rejected job '%s': %s", job_id, exc)
                return "rejected"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.evaluation_jobs.run_evaluation_job_task")
def run_evaluation_job_task(job_id: str) -> str:
    """Item 3's own literal task -- exécute un job d'évaluation en arrière-plan."""
    return asyncio.run(_run_evaluation_job_async(job_id))
