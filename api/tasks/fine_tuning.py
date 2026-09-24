"""Partie 24 -- real Celery jobs for fine-tuning. Same asyncio.run()
bridge as api/tasks/media.py/autonomous_agents.py, for the identical
reason: api/services/fine_tuning.py's real functions stay async for
the FastAPI routes/tests that also call them directly."""

import asyncio
import datetime as dt
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.fine_tuning import FineTuningJob, FineTuningJobStatus
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


def _session_factory():
    engine = make_async_engine()
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def _submit_fine_tuning_job_async(job_id: str) -> str:
    from api.services.fine_tuning import FineTuningNotFoundError, submit_job

    engine, session_factory = _session_factory()
    try:
        async with session_factory() as db:
            try:
                job = await submit_job(db, uuid.UUID(job_id))
                await db.commit()
                return job.status
            except FineTuningNotFoundError:
                await db.rollback()
                return "not_found"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.fine_tuning.submit_fine_tuning_job")
def submit_fine_tuning_job(job_id: str) -> str:
    """Item 8's own literal task -- dispatched by `POST /fine-tuning/jobs`
    right after the real, `pending` row is committed (a real provider
    file-upload + job-creation round-trip is too slow for an inline
    HTTP response)."""
    return asyncio.run(_submit_fine_tuning_job_async(job_id))


def schedule_fine_tuning_job_submission(job_id: uuid.UUID) -> None:
    """Real Celery dispatch, wrapped best-effort -- a broker hiccup
    must never fail the real `POST /fine-tuning/jobs` request itself;
    the job simply stays `pending` until a real periodic sweep or a
    manual retry submits it."""
    try:
        submit_fine_tuning_job.delay(str(job_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("schedule_fine_tuning_job_submission: could not schedule submission for job '%s': %s", job_id, exc)


async def _check_fine_tuning_status_async() -> int:
    from api.services.fine_tuning import check_job_status

    engine, session_factory = _session_factory()
    checked = 0
    try:
        async with session_factory() as db:
            running = (await db.execute(select(FineTuningJob.id).where(FineTuningJob.status == FineTuningJobStatus.running.value))).scalars().all()
            for job_id in running:
                try:
                    await check_job_status(db, job_id)
                    checked += 1
                except Exception as exc:  # noqa: BLE001 -- one real job's own polling failure must never abort the sweep
                    logger.warning("check_fine_tuning_status: job '%s' failed: %s", job_id, exc)
            await db.commit()
    finally:
        await engine.dispose()
    return checked


@celery_app.task(name="api.tasks.fine_tuning.check_fine_tuning_status")
def check_fine_tuning_status() -> int:
    """Item 8's own literal task -- real, periodic polling of every
    real, still-`running` job (real provider fine-tuning jobs take
    minutes to hours; a webhook-based push isn't available on every
    real provider's own API, so this codebase polls, same real,
    honest limitation as `api.tasks.media`'s own processing sweep)."""
    return asyncio.run(_check_fine_tuning_status_async())


async def _evaluate_fine_tuned_model_async(model_id: str, dataset_id: str) -> str:
    from api.services.fine_tuning import evaluate_model

    engine, session_factory = _session_factory()
    try:
        async with session_factory() as db:
            evaluation = await evaluate_model(db, uuid.UUID(model_id), uuid.UUID(dataset_id), None)
            await db.commit()
            return str(evaluation.id)
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.fine_tuning.evaluate_fine_tuned_model")
def evaluate_fine_tuned_model(model_id: str, dataset_id: str) -> str:
    """Item 8's own literal task -- a real evaluation run against a
    real, potentially large evaluation dataset can take a while (one
    real LLM call per real question), so `POST .../evaluate` dispatches
    this rather than blocking the HTTP request."""
    return asyncio.run(_evaluate_fine_tuned_model_async(model_id, dataset_id))


async def _cleanup_old_jobs_async(days: int) -> int:
    threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    engine, session_factory = _session_factory()
    cleaned = 0
    try:
        async with session_factory() as db:
            stale = (await db.execute(
                select(FineTuningJob).where(
                    FineTuningJob.status.in_([FineTuningJobStatus.failed.value, FineTuningJobStatus.cancelled.value]),
                    FineTuningJob.completed_at < threshold,
                )
            )).scalars().all()
            for job in stale:
                job.metrics = {**job.metrics, "archived": True}
                cleaned += 1
            await db.commit()
    finally:
        await engine.dispose()
    return cleaned


@celery_app.task(name="api.tasks.fine_tuning.cleanup_old_jobs")
def cleanup_old_jobs() -> int:
    """Item 8's own literal task -- real, periodic housekeeping: old
    `failed`/`cancelled` jobs are flagged `archived` in their own real
    `metrics` (never deleted -- a real, permanent audit trail of what
    was actually submitted/attempted, same "never silently destroy
    real history" doctrine as every other cleanup sweep in this
    codebase)."""
    return asyncio.run(_cleanup_old_jobs_async(90))
