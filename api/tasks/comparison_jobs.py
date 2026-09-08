"""Partie 7.3.4/7.3.5/7.3.6/7.3.7 -- the real Celery entry point for
`api/services/comparison_jobs.py`'s own shared `run_comparison_job` --
ONE real task backs all 4 literally-named `run_*_comparison_task`
asks, dispatched generically by `job.comparison_type` (already stored
on the real `ComparisonJob` row), same real "same standalone-engine-
per-task shape" as `api/tasks/evaluation_jobs.py`."""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.services.comparison_jobs import run_comparison_job
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_comparison_job_async(job_id: str) -> str:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            job = await run_comparison_job(db, uuid.UUID(job_id))
            return "completed" if job is not None else "not_found"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.comparison_jobs.run_comparison_job_task")
def run_comparison_job_task(job_id: str) -> str:
    """Item 5's own literal task (real, shared across 7.3.4-7.3.7's
    own `run_model_comparison_task`/`run_retriever_comparison_task`/
    `run_reranker_comparison_task`/`run_prompt_comparison_task` asks)."""
    return asyncio.run(_run_comparison_job_async(job_id))
