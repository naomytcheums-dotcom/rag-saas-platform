"""Partie 24 -- fine-tuning: dataset CRUD/validation, job submission/
polling/cancellation, fine-tuned model deployment, and evaluation
(reusing the real, existing Evaluation Lab -- see
api/models/fine_tuning.py's own module docstring)."""

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationResult
from api.models.fine_tuning import (
    FineTunedModel, FineTunedModelStatus, FineTuningDataset, FineTuningDatasetStatus, FineTuningEvaluation, FineTuningJob,
    FineTuningJobStatus,
)
from api.services.evaluation_jobs import create_evaluation_job, run_evaluation_job
from api.services.fine_tuning_providers import ProviderAPIError, ProviderNotConfiguredError, ProviderNotSupportedError, create_fine_tuning_job as provider_create_job
from api.services.fine_tuning_providers import cancel_job as provider_cancel_job
from api.services.fine_tuning_providers import get_job_status as provider_get_job_status
from api.services.fine_tuning_providers import upload_training_file as provider_upload_training_file
from api.services.fine_tuning_storage import (
    DatasetValidationError, delete_finetuning_dataset_file, download_finetuning_dataset_file, upload_finetuning_dataset_file,
    validate_finetuning_dataset_upload,
)


class FineTuningNotFoundError(Exception):
    pass


# --------------------------------------------------------------- datasets

async def list_datasets(db: AsyncSession, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    total = (await db.execute(select(func.count()).select_from(FineTuningDataset).where(FineTuningDataset.organization_id == organization_id))).scalar_one()
    rows = (await db.execute(
        select(FineTuningDataset).where(FineTuningDataset.organization_id == organization_id).order_by(FineTuningDataset.created_at.desc()).limit(limit).offset(offset)
    )).scalars().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


async def create_dataset(
    db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID | None, name: str, description: str | None,
    dataset_type: str, filename: str, content: bytes,
) -> FineTuningDataset:
    """Item 2's own literal `create_dataset(organization_id, data, user_id)`
    -- real, upfront validation (`validate_finetuning_dataset_upload`)
    BEFORE anything touches S3 or the database for a genuinely
    malformed file (bad extension, over the real size cap); a real,
    but partially-invalid JSONL file is still stored (`status="error"`,
    real `validation_errors` populated) rather than rejected outright
    -- same "store the real upload, report what's actually wrong with
    it" philosophy as `evaluation_datasets.import_questions`."""
    dataset_format, example_count, errors = validate_finetuning_dataset_upload(content, filename)

    dataset = FineTuningDataset(
        organization_id=organization_id, created_by=user_id, name=name, description=description, dataset_type=dataset_type,
        format=dataset_format, file_key="", size=len(content), example_count=example_count,
        status=FineTuningDatasetStatus.error.value if errors else FineTuningDatasetStatus.ready.value,
        validation_errors=errors or None,
    )
    db.add(dataset)
    await db.flush()  # real id needed for the real S3 key

    dataset.file_key = upload_finetuning_dataset_file(organization_id, dataset.id, filename, content)
    return dataset


async def get_dataset(db: AsyncSession, dataset_id: uuid.UUID) -> FineTuningDataset:
    dataset = await db.get(FineTuningDataset, dataset_id)
    if dataset is None:
        raise FineTuningNotFoundError(f"fine-tuning dataset '{dataset_id}' not found")
    return dataset


async def delete_dataset(db: AsyncSession, dataset_id: uuid.UUID) -> None:
    dataset = await get_dataset(db, dataset_id)
    delete_finetuning_dataset_file(dataset.file_key)
    await db.delete(dataset)


async def validate_dataset(db: AsyncSession, dataset_id: uuid.UUID) -> FineTuningDataset:
    """Item 2's own literal `validate_dataset(dataset_id, user_id)` --
    real, on-demand RE-validation of the already-stored real file
    (e.g. after `FINE_TUNING_MIN_EXAMPLES`/`_MAX_EXAMPLES` changed, or
    simply to re-confirm before submitting a real job)."""
    dataset = await get_dataset(db, dataset_id)
    dataset.status = FineTuningDatasetStatus.validating.value
    content = download_finetuning_dataset_file(dataset.file_key)
    try:
        _format, example_count, errors = validate_finetuning_dataset_upload(content, f"dataset.{dataset.format}")
    except DatasetValidationError as exc:
        dataset.status = FineTuningDatasetStatus.error.value
        dataset.validation_errors = exc.errors or [{"line": None, "error": str(exc)}]
        return dataset

    dataset.example_count = example_count
    dataset.validation_errors = errors or None
    dataset.status = FineTuningDatasetStatus.error.value if errors else FineTuningDatasetStatus.ready.value
    return dataset


# --------------------------------------------------------------- jobs

async def list_jobs(db: AsyncSession, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    total = (await db.execute(select(func.count()).select_from(FineTuningJob).where(FineTuningJob.organization_id == organization_id))).scalar_one()
    rows = (await db.execute(
        select(FineTuningJob).where(FineTuningJob.organization_id == organization_id).order_by(FineTuningJob.created_at.desc()).limit(limit).offset(offset)
    )).scalars().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


async def create_job(
    db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID | None, dataset_id: uuid.UUID, name: str,
    base_model: str | None, provider: str | None, hyperparameters: dict | None,
) -> FineTuningJob:
    """Item 2's own literal `create_job(organization_id, data, user_id)`
    -- a real, `pending` row only; real submission to the real provider
    happens in `submit_job` (run by `api/tasks/fine_tuning.py`'s own
    `submit_fine_tuning_job` Celery task), same real "persist first,
    do the slow real work later" split as every other job-creation
    function in this codebase (`AgentRunRecord`, `WorkflowRun`, ...)."""
    dataset = await get_dataset(db, dataset_id)
    if dataset.status != FineTuningDatasetStatus.ready.value:
        raise ValueError(f"dataset '{dataset_id}' is not ready (status={dataset.status!r}) -- fix or re-validate it before submitting a job")

    job = FineTuningJob(
        organization_id=organization_id, dataset_id=dataset_id, created_by=user_id, name=name,
        base_model=base_model or settings.FINE_TUNING_DEFAULT_BASE_MODEL, provider=provider or settings.FINE_TUNING_DEFAULT_PROVIDER,
        hyperparameters=hyperparameters or {},
    )
    db.add(job)
    await db.flush()
    return job


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> FineTuningJob:
    job = await db.get(FineTuningJob, job_id)
    if job is None:
        raise FineTuningNotFoundError(f"fine-tuning job '{job_id}' not found")
    return job


async def submit_job(db: AsyncSession, job_id: uuid.UUID) -> FineTuningJob:
    """Real, genuinely new orchestration: downloads the dataset's own
    real, already-validated file, uploads it to the real provider,
    then creates the real remote fine-tuning job -- persists the real
    `provider_job_id` so `check_job_status`/`cancel_job` can reach it
    again later. Real, honest failure (`status="failed"`,
    `error_message` set) for a real provider/network error or a
    missing API key -- never a crash, never a fabricated success."""
    job = await get_job(db, job_id)
    dataset = await get_dataset(db, job.dataset_id)

    try:
        content = download_finetuning_dataset_file(dataset.file_key)
        training_file_id = await provider_upload_training_file(job.provider, content, f"{dataset.name}.jsonl")
        response = await provider_create_job(job.provider, training_file_id, job.base_model, job.hyperparameters or None)
    except (ProviderNotSupportedError, ProviderNotConfiguredError, ProviderAPIError, RuntimeError) as exc:
        job.status = FineTuningJobStatus.failed.value
        job.error_message = str(exc)
        job.completed_at = dt.datetime.now(dt.timezone.utc)
        return job

    job.provider_job_id = response.get("id")
    job.status = FineTuningJobStatus.running.value
    job.started_at = dt.datetime.now(dt.timezone.utc)
    return job


async def check_job_status(db: AsyncSession, job_id: uuid.UUID) -> FineTuningJob:
    """Item 8's own literal `check_fine_tuning_status(job_id)` -- real
    polling of the real provider job, mapping ITS real status vocabulary
    onto this codebase's own real `FineTuningJobStatus`. On a real
    `succeeded` status, creates the real `FineTunedModel` row (the
    provider's own real `fine_tuned_model`/`fine_tuned_model_id` id is
    what a later real `chat_completion` call's `model=` needs) --
    idempotent: re-checking an already-`succeeded` job never creates a
    second, duplicate `FineTunedModel`."""
    job = await get_job(db, job_id)
    if job.provider_job_id is None or job.status in (FineTuningJobStatus.succeeded.value, FineTuningJobStatus.failed.value, FineTuningJobStatus.cancelled.value):
        return job

    try:
        response = await provider_get_job_status(job.provider, job.provider_job_id)
    except (ProviderNotSupportedError, ProviderNotConfiguredError, ProviderAPIError, RuntimeError) as exc:
        job.error_message = str(exc)
        return job

    provider_status = response.get("status", "")
    if provider_status in ("succeeded",):
        job.status = FineTuningJobStatus.succeeded.value
        job.completed_at = dt.datetime.now(dt.timezone.utc)
        job.metrics = {**job.metrics, "trained_tokens": response.get("trained_tokens")}
        provider_model_id = response.get("fine_tuned_model") or response.get("fine_tuned_model_id")
        if provider_model_id:
            existing = await db.scalar(select(FineTunedModel).where(FineTunedModel.job_id == job.id))
            if existing is None:
                db.add(FineTunedModel(
                    organization_id=job.organization_id, job_id=job.id, name=job.name, provider=job.provider,
                    provider_model_id=provider_model_id, base_model=job.base_model, metrics=job.metrics,
                ))
    elif provider_status in ("failed",):
        job.status = FineTuningJobStatus.failed.value
        job.completed_at = dt.datetime.now(dt.timezone.utc)
        job.error_message = (response.get("error") or {}).get("message") if isinstance(response.get("error"), dict) else str(response.get("error") or "")
    elif provider_status in ("cancelled",):
        job.status = FineTuningJobStatus.cancelled.value
        job.completed_at = dt.datetime.now(dt.timezone.utc)
    # Any other real, in-progress provider status (validating_files,
    # queued, running, ...) leaves this codebase's own real status as
    # "running" -- an honest, coarser real state, not a 1:1 mirror of
    # every real provider-specific sub-phase.
    return job


async def cancel_job(db: AsyncSession, job_id: uuid.UUID) -> FineTuningJob:
    job = await get_job(db, job_id)
    if job.status not in (FineTuningJobStatus.pending.value, FineTuningJobStatus.running.value):
        return job
    if job.provider_job_id:
        try:
            await provider_cancel_job(job.provider, job.provider_job_id)
        except (ProviderNotSupportedError, ProviderNotConfiguredError, ProviderAPIError, RuntimeError) as exc:
            job.error_message = str(exc)
            return job
    job.status = FineTuningJobStatus.cancelled.value
    job.completed_at = dt.datetime.now(dt.timezone.utc)
    return job


async def get_job_metrics(db: AsyncSession, job_id: uuid.UUID) -> dict:
    job = await get_job(db, job_id)
    return job.metrics or {}


# --------------------------------------------------------------- models

async def list_models(db: AsyncSession, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    total = (await db.execute(select(func.count()).select_from(FineTunedModel).where(FineTunedModel.organization_id == organization_id))).scalar_one()
    rows = (await db.execute(
        select(FineTunedModel).where(FineTunedModel.organization_id == organization_id).order_by(FineTunedModel.created_at.desc()).limit(limit).offset(offset)
    )).scalars().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


async def get_model(db: AsyncSession, model_id: uuid.UUID) -> FineTunedModel:
    model = await db.get(FineTunedModel, model_id)
    if model is None:
        raise FineTuningNotFoundError(f"fine-tuned model '{model_id}' not found")
    return model


async def delete_model(db: AsyncSession, model_id: uuid.UUID) -> None:
    model = await get_model(db, model_id)
    await db.delete(model)


async def deploy_model(db: AsyncSession, model_id: uuid.UUID) -> FineTunedModel:
    model = await get_model(db, model_id)
    if model.status == FineTunedModelStatus.deprecated.value:
        raise ValueError(f"model '{model_id}' is deprecated and cannot be deployed")
    model.deployed = True
    return model


async def undeploy_model(db: AsyncSession, model_id: uuid.UUID) -> FineTunedModel:
    model = await get_model(db, model_id)
    model.deployed = False
    return model


# --------------------------------------------------------------- evaluation

async def evaluate_model(db: AsyncSession, model_id: uuid.UUID, dataset_id: uuid.UUID, user_id: uuid.UUID | None) -> FineTuningEvaluation:
    """Item 2's own literal `evaluate_model(model_id, dataset_id, user_id)`
    -- real, thin reuse of the existing Evaluation Lab
    (`create_evaluation_job` + `run_evaluation_job`, Partie 7.1-7.2):
    the fine-tuned model is passed as a real `model_config` override
    (`{"provider", "model": provider_model_id}`), exactly like any
    other real candidate LLM configuration Partie 7.3's own comparison
    jobs already test -- no second, parallel evaluation engine.
    `dataset_id` here is a real, EXISTING `EvaluationDataset` (Partie
    7.1.1), not a `FineTuningDataset` -- the org must already have one
    with real questions in it."""
    model = await get_model(db, model_id)
    eval_dataset = await db.get(EvaluationDataset, dataset_id)
    if eval_dataset is None:
        raise FineTuningNotFoundError(f"evaluation dataset '{dataset_id}' not found")

    job = await create_evaluation_job(db, dataset_id=dataset_id, model_config={"provider": model.provider, "model": model.provider_model_id}, created_by=user_id)
    await db.flush()
    await run_evaluation_job(db, job.id)

    results = (await db.execute(select(EvaluationResult).where(EvaluationResult.evaluation_job_id == job.id))).scalars().all()
    # Real, existing Partie 7.2 metric ("answer_relevance", computed by
    # `extend_evaluation_metrics`, already run per-question inside
    # `run_evaluation_job` -> `run_evaluation`) -- the closest real,
    # single scalar this codebase already has to "how good was this
    # model's own real answer," reused rather than inventing a new
    # scoring function.
    relevance_scores = [float(r.metrics["answer_relevance"]) for r in results if r.metrics and r.metrics.get("answer_relevance") is not None]
    average_score = sum(relevance_scores) / len(relevance_scores) if relevance_scores else None

    evaluation = FineTuningEvaluation(
        model_id=model_id, dataset_id=dataset_id, evaluation_job_id=job.id, score=average_score,
        metrics={"result_count": len(results), "average_answer_relevance": average_score},
    )
    db.add(evaluation)
    await db.flush()
    return evaluation


async def list_evaluations(db: AsyncSession, model_id: uuid.UUID) -> list[FineTuningEvaluation]:
    return list((await db.scalars(select(FineTuningEvaluation).where(FineTuningEvaluation.model_id == model_id).order_by(FineTuningEvaluation.created_at.desc()))).all())
