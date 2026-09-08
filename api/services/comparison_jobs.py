"""
Partie 7.3.4/7.3.5/7.3.6/7.3.7 -- ONE real, shared, persisted
comparison engine, not 4 real, near-duplicate ones. Item 1's own
literal column list for Model/Retriever/Reranker/Prompt comparison is
STRUCTURALLY IDENTICAL across all 4 (`id`, `dataset_id`, `name`, a real
list of candidates, `results`, `created_by`, `created_at`,
`completed_at`); item 2's own literal function list is the SAME 6
real shapes (`create_*`, `run_*`, `get_*`, `list_*`, `compare_*`,
`get_*_results`) under 4 different real names.

**Real, per-type variant meaning, ONE real dispatch table**: a
"model" variant is a real dict (an LLM `model_config` override,
`run_evaluation`'s own existing real parameter, Partie 7.2.1); a
"prompt" variant is a real, plain STRING that becomes
`model_config={"system_prompt": variant}` -- Partie 7.2.9's own
`resolve_system_prompt` already resolves this exact real override, so
comparing prompts needs zero new real machinery. A "retriever"
variant is a real, plain STRING strategy name (`search_with_context`
already accepts a real `strategy` override directly, Partie 3.3.x); a
"reranker" variant is a real, plain STRING model name, normalized to
`{"strategy": "hybrid_reranked", "reranker": variant}` -- a real
reranker override is only ever real-ily APPLIED under that one real
strategy (see `retrieval_pipeline.search`'s own real dispatch), so
this module normalizes it rather than silently shipping an inert
comparison. `run_evaluation`'s own new `retrieval_overrides` parameter
(added this same étape) is what makes retriever/reranker comparisons
possible at all without a second retrieval+generation pipeline.

**`compare_*`/`run_*`, two real, honest names for the one real
operation**: same real "two names, one already-idempotent function"
precedent as `process_batch_job_task`/`resume_batch_job_task` (Partie
2.2.16) -- item 2's own literal ask lists BOTH `run_model_comparison`
AND `compare_models` with the identical real `(comparison_id)`
signature.

**Robustesse (vision critique 3) -- un variant échoue**: same real,
per-item resilience as `run_evaluation_job` (7.3.1) -- one real
variant/question's own real failure is logged and skipped, never
aborting the rest of the real comparison."""

import datetime as dt
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.evaluation import ComparisonJob, ComparisonType, EvaluationQuestion
from api.services.evaluation_comparisons import metric_keys
from api.services.evaluation_results import run_evaluation
from api.services.retrieval_metrics import summarize_metric_for_results

logger = logging.getLogger(__name__)

KNOWN_RETRIEVAL_STRATEGIES = ("hybrid", "vector_only", "bm25_only", "hybrid_reranked", "semantic")


def _validate_variants(comparison_type: str, variants: list) -> None:
    if not variants:
        raise ValueError("At least one real variant is required")
    if comparison_type == ComparisonType.retriever:
        for v in variants:
            if v not in KNOWN_RETRIEVAL_STRATEGIES:
                raise ValueError(f"Unknown retrieval strategy: {v!r} (expected one of {KNOWN_RETRIEVAL_STRATEGIES})")
    elif comparison_type == ComparisonType.model:
        for v in variants:
            if not isinstance(v, dict):
                raise ValueError(f"A real 'model' variant must be a dict, got {v!r}")


def _variant_kwargs(comparison_type: str, variant) -> dict:
    """Real, per-type dispatch -- see this module's own top docstring."""
    if comparison_type == ComparisonType.model:
        return {"model_config": variant}
    if comparison_type == ComparisonType.prompt:
        return {"model_config": {"system_prompt": variant}}
    if comparison_type == ComparisonType.retriever:
        return {"retrieval_overrides": {"strategy": variant}}
    if comparison_type == ComparisonType.reranker:
        return {"retrieval_overrides": {"strategy": "hybrid_reranked", "reranker": variant}}
    raise ValueError(f"Unknown comparison_type: {comparison_type!r}")


async def _create_comparison_job(
    db: AsyncSession, dataset_id: uuid.UUID, comparison_type: str, name: str, variants: list, created_by: uuid.UUID | None,
) -> ComparisonJob:
    _validate_variants(comparison_type, variants)
    job = ComparisonJob(dataset_id=dataset_id, comparison_type=comparison_type, name=name, variants=variants, created_by=created_by)
    db.add(job)
    await db.flush()
    return job


async def run_comparison_job(db: AsyncSession, job_id: uuid.UUID) -> ComparisonJob | None:
    """The one real, shared engine every `run_*_comparison`/`compare_*`
    literal function below routes through."""
    job = await db.get(ComparisonJob, job_id)
    if job is None:
        return None
    comparison_type = job.comparison_type
    variants = list(job.variants)

    # Real, plain UUIDs captured upfront -- same real reasoning as
    # run_evaluation_job's own fix: a real per-question `db.rollback()`
    # below would otherwise expire every real ORM object still tracked
    # by the session, including any not-yet-processed real question.
    question_ids = [
        q.id for q in (await db.scalars(
            select(EvaluationQuestion).where(EvaluationQuestion.dataset_id == job.dataset_id).order_by(EvaluationQuestion.created_at)
        )).all()
    ]

    keys = metric_keys()
    variant_results = []
    for variant in variants:
        result_ids = []
        for question_id in question_ids:
            try:
                result = await run_evaluation(db, question_id, **_variant_kwargs(comparison_type, variant))
                if result is not None:
                    result_ids.append(result.id)
            except Exception as exc:  # noqa: BLE001 -- one real variant/question's own failure must never abort the whole comparison
                logger.warning("run_comparison_job: variant %r, question '%s' of job '%s' failed: %s", variant, question_id, job_id, exc)
                await db.rollback()
                await db.refresh(job)
        metrics = {key: await summarize_metric_for_results(db, result_ids, key) for key in keys}
        variant_results.append({"variant": variant, "result_ids": [str(rid) for rid in result_ids], "metrics": metrics})

    rank_metric = settings.EVALUATION_DEFAULT_COMPARISON_METRIC
    ranking = sorted(range(len(variant_results)), key=lambda i: variant_results[i]["metrics"][rank_metric]["average"] or 0.0, reverse=True)
    job.results = {
        "sample_size": len(question_ids), "rank_metric": rank_metric, "ranking": ranking, "variants": variant_results,
    }
    job.completed_at = dt.datetime.now(dt.timezone.utc)
    await db.commit()
    await db.refresh(job)
    return job


async def _get_comparison_job(db: AsyncSession, comparison_id: uuid.UUID) -> ComparisonJob | None:
    return await db.get(ComparisonJob, comparison_id)


async def _list_comparison_jobs(db: AsyncSession, dataset_id: uuid.UUID, comparison_type: str, limit: int = 50, offset: int = 0) -> dict:
    conditions = [ComparisonJob.dataset_id == dataset_id, ComparisonJob.comparison_type == comparison_type]
    total = await db.scalar(select(func.count()).select_from(ComparisonJob).where(*conditions)) or 0
    rows = (await db.scalars(
        select(ComparisonJob).where(*conditions).order_by(ComparisonJob.created_at.desc()).limit(limit).offset(offset)
    )).all()
    return {"items": list(rows), "total": total, "limit": limit, "offset": offset}


def schedule_comparison_job_processing(job_id: uuid.UUID) -> None:
    """Real Celery dispatch, wrapped best-effort -- same real reasoning
    as `evaluation_jobs.schedule_evaluation_job_processing`."""
    from api.tasks.comparison_jobs import run_comparison_job_task

    try:
        run_comparison_job_task.delay(str(job_id))
    except Exception as exc:  # noqa: BLE001 -- a broker hiccup must never break the create request
        logger.warning("schedule_comparison_job_processing: could not schedule job '%s': %s", job_id, exc)


# --------------------------------------- 7.3.4 -- Model comparison --

async def create_model_comparison(db: AsyncSession, dataset_id: uuid.UUID, name: str, model_configs: list[dict], created_by: uuid.UUID | None = None) -> ComparisonJob:
    return await _create_comparison_job(db, dataset_id, ComparisonType.model, name, model_configs, created_by)


async def run_model_comparison(db: AsyncSession, comparison_id: uuid.UUID) -> ComparisonJob | None:
    return await run_comparison_job(db, comparison_id)


compare_models = run_model_comparison


async def get_model_comparison(db: AsyncSession, comparison_id: uuid.UUID) -> ComparisonJob | None:
    return await _get_comparison_job(db, comparison_id)


async def list_model_comparisons(db: AsyncSession, dataset_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    return await _list_comparison_jobs(db, dataset_id, ComparisonType.model, limit, offset)


async def get_comparison_results(db: AsyncSession, comparison_id: uuid.UUID) -> dict | None:
    """Item 2's own literal function (7.3.4) -- real, thin extraction
    of `job.results` alone (vs. `get_model_comparison`'s own real,
    whole-row return)."""
    job = await db.get(ComparisonJob, comparison_id)
    return job.results if job is not None else None


# --------------------------------------- 7.3.5 -- Retriever comparison --

async def create_retriever_comparison(db: AsyncSession, dataset_id: uuid.UUID, name: str, retrievers: list[str], created_by: uuid.UUID | None = None) -> ComparisonJob:
    return await _create_comparison_job(db, dataset_id, ComparisonType.retriever, name, retrievers, created_by)


async def run_retriever_comparison(db: AsyncSession, comparison_id: uuid.UUID) -> ComparisonJob | None:
    return await run_comparison_job(db, comparison_id)


compare_retrievers = run_retriever_comparison


async def get_retriever_comparison(db: AsyncSession, comparison_id: uuid.UUID) -> ComparisonJob | None:
    return await _get_comparison_job(db, comparison_id)


async def list_retriever_comparisons(db: AsyncSession, dataset_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    return await _list_comparison_jobs(db, dataset_id, ComparisonType.retriever, limit, offset)


async def get_retriever_comparison_results(db: AsyncSession, comparison_id: uuid.UUID) -> dict | None:
    return await get_comparison_results(db, comparison_id)


# --------------------------------------- 7.3.6 -- Reranker comparison --

async def create_reranker_comparison(db: AsyncSession, dataset_id: uuid.UUID, name: str, rerankers: list[str], created_by: uuid.UUID | None = None) -> ComparisonJob:
    return await _create_comparison_job(db, dataset_id, ComparisonType.reranker, name, rerankers, created_by)


async def run_reranker_comparison(db: AsyncSession, comparison_id: uuid.UUID) -> ComparisonJob | None:
    return await run_comparison_job(db, comparison_id)


compare_rerankers = run_reranker_comparison


async def get_reranker_comparison(db: AsyncSession, comparison_id: uuid.UUID) -> ComparisonJob | None:
    return await _get_comparison_job(db, comparison_id)


async def list_reranker_comparisons(db: AsyncSession, dataset_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    return await _list_comparison_jobs(db, dataset_id, ComparisonType.reranker, limit, offset)


async def get_reranker_comparison_results(db: AsyncSession, comparison_id: uuid.UUID) -> dict | None:
    return await get_comparison_results(db, comparison_id)


# --------------------------------------- 7.3.7 -- Prompt comparison --

async def create_prompt_comparison(db: AsyncSession, dataset_id: uuid.UUID, name: str, prompts: list[str], created_by: uuid.UUID | None = None) -> ComparisonJob:
    return await _create_comparison_job(db, dataset_id, ComparisonType.prompt, name, prompts, created_by)


async def run_prompt_comparison(db: AsyncSession, comparison_id: uuid.UUID) -> ComparisonJob | None:
    return await run_comparison_job(db, comparison_id)


compare_prompts = run_prompt_comparison


async def get_prompt_comparison(db: AsyncSession, comparison_id: uuid.UUID) -> ComparisonJob | None:
    return await _get_comparison_job(db, comparison_id)


async def list_prompt_comparisons(db: AsyncSession, dataset_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    return await _list_comparison_jobs(db, dataset_id, ComparisonType.prompt, limit, offset)


async def get_prompt_comparison_results(db: AsyncSession, comparison_id: uuid.UUID) -> dict | None:
    return await get_comparison_results(db, comparison_id)
