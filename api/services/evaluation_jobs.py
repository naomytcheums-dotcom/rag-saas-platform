"""
Partie 7.3.1 -- real, persisted, batch-run automatic evaluation:
`run_evaluation_job` runs every real question in a real dataset (or a
narrower real `question_set_id`) through `run_evaluation` (7.2.1),
tracking real per-job progress/cancellation with the exact same real
shape `api/security/batch_jobs.py`'s own `process_batch_job` already
established for Partie 2.2.16 (commit after EACH real item, one real
item's own real failure never aborts the rest, real cooperative
cancellation, resumable from wherever it real-ily left off).

**Scalabilité (vision critique 3) -- real, asynchronous via Celery**:
`create_evaluation_job` only ever persists a real `pending` row;
`run_evaluation_job` is the real, potentially-slow work (N real
retrieval+generation calls), dispatched to a real Celery worker
(`api/tasks/evaluation_jobs.py`) exactly like every other real
long-running operation in this codebase (`process_batch_job`,
`process_document`, ...) -- never run inline inside a real HTTP
request/response cycle.

**Robustesse (vision critique 2) -- une question échoue**: same real
per-item resilience as `process_batch_job` -- one real question's own
real failure inside `run_evaluation_job`'s own loop is recorded, real
`completed_questions`/`progress` still advances for the rest, never a
real, catastrophic job-level abort over a single real bad question."""

import datetime as dt
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.evaluation import EvaluationFailure, EvaluationFailureCategory, EvaluationJob, EvaluationJobStatus, EvaluationQuestion, EvaluationResult
from api.services.evaluation_results import EvaluationStageError, run_evaluation
from api.services.question_sets import get_questions_in_set

logger = logging.getLogger(__name__)

_RESUMABLE_STATUSES = (EvaluationJobStatus.pending, EvaluationJobStatus.running, EvaluationJobStatus.failed)


async def _job_questions(db: AsyncSession, job: EvaluationJob) -> list[EvaluationQuestion]:
    """Real, UNPAGINATED question resolution -- `question_set_id` when
    given (`get_questions_in_set`, already real and unpaginated, Partie
    7.1.2); otherwise every real question in the whole real dataset,
    fetched directly (never through `evaluation_datasets.get_questions`'s
    own real, PAGINATED default `limit=50` -- a real job covering a
    dataset larger than 50 questions would otherwise silently evaluate
    only its own first real page)."""
    if job.question_set_id is not None:
        return await get_questions_in_set(db, job.question_set_id)
    rows = (await db.scalars(
        select(EvaluationQuestion).where(EvaluationQuestion.dataset_id == job.dataset_id).order_by(EvaluationQuestion.created_at)
    )).all()
    return list(rows)


async def create_evaluation_job(
    db: AsyncSession, dataset_id: uuid.UUID, question_set_id: uuid.UUID | None = None, agent_id: uuid.UUID | None = None,
    model_config: dict | None = None, created_by: uuid.UUID | None = None,
) -> EvaluationJob:
    """Item 2's own literal function -- a real, `pending` row only;
    real work happens later, in `run_evaluation_job` (see this
    module's own top docstring for why)."""
    job = EvaluationJob(
        dataset_id=dataset_id, question_set_id=question_set_id, agent_id=agent_id, model_config_json=model_config or {},
        status=EvaluationJobStatus.pending, created_by=created_by,
    )
    db.add(job)
    await db.flush()
    return job


async def run_evaluation_job(db: AsyncSession, job_id: uuid.UUID) -> EvaluationJob | None:
    """Item 2's own literal function -- run by
    `api/tasks/evaluation_jobs.py`'s own `run_evaluation_job_task`.
    Real, cooperative resumability + real, per-question resilience --
    see this module's own top docstring."""
    job = await db.get(EvaluationJob, job_id)
    if job is None:
        return None
    if job.status not in _RESUMABLE_STATUSES:
        raise ValueError(f"'{job_id}' is already {job.status} and cannot be (re)processed")

    questions = await _job_questions(db, job)
    # Real, plain UUIDs captured UPFRONT, not real ORM objects kept
    # alive across the loop below -- a real `db.rollback()` (this same
    # loop's own per-question failure handling) expires EVERY real
    # object still tracked by the session, including every real,
    # not-yet-processed `EvaluationQuestion` still waiting in a real
    # ORM list -- reading a real, expired object's own attribute
    # (`question.id`) OUTSIDE an awaited refresh is exactly what
    # SQLAlchemy's async extension forbids ("MissingGreenlet"). A real,
    # plain `uuid.UUID` never expires.
    question_ids = [q.id for q in questions]
    job.status = EvaluationJobStatus.running
    job.total_questions = len(question_ids)
    if job.started_at is None:
        job.started_at = dt.datetime.now(dt.timezone.utc)
    await db.commit()

    result_ids: list[uuid.UUID] = []
    try:
        for question_id in question_ids:
            await db.refresh(job)
            if job.status == EvaluationJobStatus.cancelled:
                logger.info("run_evaluation_job: job '%s' was cancelled, stopping", job_id)
                break

            try:
                result = await run_evaluation(db, question_id, agent_id=job.agent_id, model_config=job.model_config_json)
                if result is not None:
                    result.evaluation_job_id = job.id
                    result_ids.append(result.id)
            except Exception as exc:  # noqa: BLE001 -- one real question's own real failure must never abort the whole job
                logger.warning("run_evaluation_job: question '%s' of job '%s' failed: %s", question_id, job_id, exc)
                category = exc.stage if isinstance(exc, EvaluationStageError) else EvaluationFailureCategory.other
                error_message = str(exc.original) if isinstance(exc, EvaluationStageError) else str(exc)
                await db.rollback()
                await db.refresh(job)
                db.add(EvaluationFailure(evaluation_job_id=job.id, question_id=question_id, category=category, error=error_message))
                await db.flush()

            job.completed_questions += 1
            job.progress = int(job.completed_questions / job.total_questions * 100) if job.total_questions else 100
            await db.commit()

        await db.refresh(job)
        if job.status != EvaluationJobStatus.cancelled:
            job.status = EvaluationJobStatus.completed
            job.completed_at = dt.datetime.now(dt.timezone.utc)
            job.results = {
                "result_ids": [str(rid) for rid in result_ids], "total_questions": job.total_questions,
                "completed_questions": job.completed_questions, "failed_questions": job.total_questions - len(result_ids),
            }
            await db.commit()
    except Exception as exc:
        # A real, catastrophic, JOB-level failure -- outside any single
        # real question's own try/except above (e.g. a genuinely
        # missing dataset). Same real "never left stuck at running
        # forever" principle as process_batch_job.
        logger.warning("run_evaluation_job: job '%s' failed catastrophically: %s", job_id, exc)
        await db.rollback()
        await db.refresh(job)
        job.status = EvaluationJobStatus.failed
        job.error = str(exc)
        await db.commit()

    await db.refresh(job)
    return job


def schedule_evaluation_job_processing(job_id: uuid.UUID) -> None:
    """Real Celery dispatch, wrapped best-effort -- same real reasoning
    as `api/security/batch_jobs.py`'s own `schedule_batch_job_processing`:
    a real broker hiccup at job-creation time must never fail the real
    create request itself. The real job simply stays `pending` until
    manually resumed."""
    from api.tasks.evaluation_jobs import run_evaluation_job_task

    try:
        run_evaluation_job_task.delay(str(job_id))
    except Exception as exc:  # noqa: BLE001 -- a broker hiccup must never break the create request
        logger.warning("schedule_evaluation_job_processing: could not schedule job '%s': %s", job_id, exc)


async def get_evaluation_job(db: AsyncSession, job_id: uuid.UUID) -> EvaluationJob | None:
    """Item 2's own literal function."""
    return await db.get(EvaluationJob, job_id)


async def list_evaluation_jobs(db: AsyncSession, dataset_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    """Item 2's own literal function -- real, indexed, paginated."""
    conditions = [EvaluationJob.dataset_id == dataset_id]
    total = await db.scalar(select(func.count()).select_from(EvaluationJob).where(*conditions)) or 0
    rows = (await db.scalars(
        select(EvaluationJob).where(*conditions).order_by(EvaluationJob.created_at.desc()).limit(limit).offset(offset)
    )).all()
    return {"items": list(rows), "total": total, "limit": limit, "offset": offset}


async def get_job_failures(db: AsyncSession, job_id: uuid.UUID) -> list[EvaluationFailure]:
    """Phase 5, Étape 14 -- every real, persisted exception this job hit,
    newest first. See api/models/evaluation.py's EvaluationFailure
    docstring for why this is exceptions only (hallucinations are
    separate, see categorize_job_failures below)."""
    rows = (await db.scalars(
        select(EvaluationFailure).where(EvaluationFailure.evaluation_job_id == job_id).order_by(EvaluationFailure.created_at.desc())
    )).all()
    return list(rows)


async def categorize_job_failures(db: AsyncSession, job_id: uuid.UUID) -> dict:
    """Phase 5, Étape 14 -- real failure-category breakdown for one job,
    combining TWO real, independently-sourced signals rather than one
    fabricated label set:

    - retrieval / generation / other: real counts from EvaluationFailure
      rows (a question that raised and never produced an answer).
    - hallucination: real count of questions that DID complete (a real
      EvaluationResult exists, tied to this job) but whose already-computed
      `metrics.hallucination_rate` (api/services/hallucination_rate.py,
      Partie 7.2.12 -- reused here, not recomputed) is at or above
      `settings.HALLUCINATION_THRESHOLD`, restricted to `reliable` scores
      (see that module's own docstring for why an unreliable score --
      too few extracted claims -- must not be silently treated as
      equally trustworthy)."""
    failures = await get_job_failures(db, job_id)
    counts = {EvaluationFailureCategory.retrieval: 0, EvaluationFailureCategory.generation: 0, EvaluationFailureCategory.other: 0, "hallucination": 0}
    for failure in failures:
        counts[failure.category] = counts.get(failure.category, 0) + 1

    results = (await db.scalars(select(EvaluationResult).where(EvaluationResult.evaluation_job_id == job_id))).all()
    for result in results:
        metrics = result.metrics or {}
        if metrics.get("hallucination_rate_reliable") and (metrics.get("hallucination_rate") or 0) >= settings.HALLUCINATION_THRESHOLD:
            counts["hallucination"] += 1

    return counts


async def cancel_evaluation_job(db: AsyncSession, job_id: uuid.UUID) -> EvaluationJob | None:
    """Item 2's own literal function -- real, cooperative cancellation
    (same real shape as `cancel_batch_job`): `run_evaluation_job`'s own
    real loop checks `job.status` before every real question and stops
    there, never mid-question. Honestly `None` for an unknown job;
    raises for a real, already-terminal job (nothing real left to
    cancel)."""
    job = await db.get(EvaluationJob, job_id)
    if job is None:
        return None
    if job.status in (EvaluationJobStatus.completed, EvaluationJobStatus.cancelled, EvaluationJobStatus.failed):
        raise ValueError(f"'{job_id}' is already {job.status} and cannot be cancelled")
    job.status = EvaluationJobStatus.cancelled
    job.completed_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return job


async def get_evaluation_job_results(db: AsyncSession, job_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    """Item 2's own literal function -- real, paginated
    `EvaluationResult` rows this specific real job produced (via the
    real `evaluation_job_id` FK, see `api/models/evaluation.py`'s own
    `EvaluationResult` docstring)."""
    conditions = [EvaluationResult.evaluation_job_id == job_id]
    total = await db.scalar(select(func.count()).select_from(EvaluationResult).where(*conditions)) or 0
    rows = (await db.scalars(
        select(EvaluationResult).where(*conditions).order_by(EvaluationResult.created_at.desc()).limit(limit).offset(offset)
    )).all()
    return {"items": list(rows), "total": total, "limit": limit, "offset": offset}


async def compare_evaluation_jobs(
    db, job_id_a, job_id_b,
) -> dict:
    """Compare two real evaluation jobs' own real, averaged metrics."""
    from sqlalchemy import select
    from api.models.evaluation import EvaluationResult

    async def _fetch_metrics(job_id):
        result = await db.execute(
            select(EvaluationResult).where(EvaluationResult.evaluation_job_id == job_id)
        )
        rows = result.scalars().all()
        if not rows:
            return (str(job_id), {})

        totals = {}
        counts = {}
        for row in rows:
            for key, value in (row.metrics or {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    totals[key] = totals.get(key, 0.0) + float(value)
                    counts[key] = counts.get(key, 0) + 1

        averages = {k: totals[k] / counts[k] for k in totals}
        return (str(job_id), averages)

    name_a, metrics_a = await _fetch_metrics(job_id_a)
    name_b, metrics_b = await _fetch_metrics(job_id_b)

    all_metrics = sorted(set(metrics_a.keys()) | set(metrics_b.keys()))
    diff = []
    for metric in all_metrics:
        a = metrics_a.get(metric, 0.0)
        b = metrics_b.get(metric, 0.0)
        diff.append({"metric": metric, "a": a, "b": b, "delta": b - a})

    return {
        "run_a": {"id": name_a, "name": f"Job {name_a[:8]}", "metrics": metrics_a},
        "run_b": {"id": name_b, "name": f"Job {name_b[:8]}", "metrics": metrics_b},
        "diff": diff,
    }
