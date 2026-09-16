"""Partie 24 -- fine-tuning endpoints. Org-scoped list/create routes
reuse `require_org_member`/`require_org_admin` directly; single-
resource routes use `require_dataset_*`/`require_job_*`/`require_model_*`
(api/security/fine_tuning.py), flat `/fine-tuning/{resource}/{id}`
paths -- same access-level adaptation already applied for Parties
19-23. `dataset_id`/`job_id`/`model_id` here are Partie 24's own
resource ids, not an `{org_id}` -- the literal spec's own endpoint
paths never nest under an organization, unlike Parties 22/23's own
list/create routes. List/create endpoints therefore take a real,
required `org_id` QUERY parameter instead (`require_org_member`/
`require_org_admin` resolve it the same way either way -- FastAPI
matches a dependency's own parameter name against path params first,
then query params)."""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.fine_tuning import FineTunedModel, FineTuningDataset, FineTuningJob
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.fine_tuning import (
    FineTunedModelListResponse, FineTunedModelResponse, FineTuningDatasetListResponse, FineTuningDatasetResponse,
    FineTuningEvaluateRequest, FineTuningEvaluationResponse, FineTuningJobCreateRequest, FineTuningJobListResponse,
    FineTuningJobResponse,
)
from api.security.fine_tuning import (
    require_dataset_admin, require_dataset_member, require_job_admin, require_job_member, require_model_admin,
    require_model_member,
)
from api.security.organizations import require_org_admin, require_org_member
from api.services import fine_tuning as fine_tuning_service
from api.services.fine_tuning_storage import DatasetValidationError
from api.tasks.fine_tuning import schedule_fine_tuning_job_submission

router = APIRouter(tags=["fine-tuning"])


# --------------------------------------------------------------- datasets

@router.get("/fine-tuning/datasets", response_model=FineTuningDatasetListResponse)
async def list_datasets_endpoint(org_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await fine_tuning_service.list_datasets(db, org_id, limit, offset)


@router.post("/fine-tuning/datasets", response_model=FineTuningDatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset_endpoint(
    org_id: uuid.UUID, name: str = Form(...), description: str | None = Form(None), dataset_type: str = Form("llm"),
    file: UploadFile = File(...), _caller: OrganizationMember = Depends(require_org_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    try:
        dataset = await fine_tuning_service.create_dataset(db, org_id, current_user.id, name, description, dataset_type, file.filename or "dataset.jsonl", content)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.get("/fine-tuning/datasets/{dataset_id}", response_model=FineTuningDatasetResponse)
async def get_dataset_endpoint(dataset_ctx: tuple[FineTuningDataset, OrganizationMember] = Depends(require_dataset_member)):
    dataset, _caller = dataset_ctx
    return dataset


@router.delete("/fine-tuning/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset_endpoint(dataset_ctx: tuple[FineTuningDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db)):
    dataset, _caller = dataset_ctx
    await fine_tuning_service.delete_dataset(db, dataset.id)
    await db.commit()


@router.post("/fine-tuning/datasets/{dataset_id}/validate", response_model=FineTuningDatasetResponse)
async def validate_dataset_endpoint(dataset_ctx: tuple[FineTuningDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db)):
    dataset, _caller = dataset_ctx
    updated = await fine_tuning_service.validate_dataset(db, dataset.id)
    await db.commit()
    await db.refresh(updated)
    return updated


# --------------------------------------------------------------- jobs

@router.get("/fine-tuning/jobs", response_model=FineTuningJobListResponse)
async def list_jobs_endpoint(org_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await fine_tuning_service.list_jobs(db, org_id, limit, offset)


@router.post("/fine-tuning/jobs", response_model=FineTuningJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job_endpoint(
    org_id: uuid.UUID, payload: FineTuningJobCreateRequest, _caller: OrganizationMember = Depends(require_org_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    try:
        job = await fine_tuning_service.create_job(
            db, org_id, current_user.id, payload.dataset_id, payload.name, payload.base_model, payload.provider, payload.hyperparameters,
        )
    except (ValueError, fine_tuning_service.FineTuningNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(job)
    schedule_fine_tuning_job_submission(job.id)
    return job


@router.get("/fine-tuning/jobs/{job_id}", response_model=FineTuningJobResponse)
async def get_job_endpoint(job_ctx: tuple[FineTuningJob, OrganizationMember] = Depends(require_job_member)):
    job, _caller = job_ctx
    return job


@router.post("/fine-tuning/jobs/{job_id}/cancel", response_model=FineTuningJobResponse)
async def cancel_job_endpoint(job_ctx: tuple[FineTuningJob, OrganizationMember] = Depends(require_job_admin), db: AsyncSession = Depends(get_db)):
    job, _caller = job_ctx
    updated = await fine_tuning_service.cancel_job(db, job.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.get("/fine-tuning/jobs/{job_id}/metrics")
async def get_job_metrics_endpoint(job_ctx: tuple[FineTuningJob, OrganizationMember] = Depends(require_job_member), db: AsyncSession = Depends(get_db)):
    job, _caller = job_ctx
    return await fine_tuning_service.get_job_metrics(db, job.id)


# --------------------------------------------------------------- models

@router.get("/fine-tuning/models", response_model=FineTunedModelListResponse)
async def list_models_endpoint(org_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await fine_tuning_service.list_models(db, org_id, limit, offset)


@router.get("/fine-tuning/models/{model_id}", response_model=FineTunedModelResponse)
async def get_model_endpoint(model_ctx: tuple[FineTunedModel, OrganizationMember] = Depends(require_model_member)):
    model, _caller = model_ctx
    return model


@router.delete("/fine-tuning/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_endpoint(model_ctx: tuple[FineTunedModel, OrganizationMember] = Depends(require_model_admin), db: AsyncSession = Depends(get_db)):
    model, _caller = model_ctx
    await fine_tuning_service.delete_model(db, model.id)
    await db.commit()


@router.post("/fine-tuning/models/{model_id}/deploy", response_model=FineTunedModelResponse)
async def deploy_model_endpoint(model_ctx: tuple[FineTunedModel, OrganizationMember] = Depends(require_model_admin), db: AsyncSession = Depends(get_db)):
    model, _caller = model_ctx
    try:
        updated = await fine_tuning_service.deploy_model(db, model.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/fine-tuning/models/{model_id}/undeploy", response_model=FineTunedModelResponse)
async def undeploy_model_endpoint(model_ctx: tuple[FineTunedModel, OrganizationMember] = Depends(require_model_admin), db: AsyncSession = Depends(get_db)):
    model, _caller = model_ctx
    updated = await fine_tuning_service.undeploy_model(db, model.id)
    await db.commit()
    await db.refresh(updated)
    return updated


# --------------------------------------------------------------- evaluation

@router.post("/fine-tuning/models/{model_id}/evaluate", response_model=FineTuningEvaluationResponse, status_code=status.HTTP_201_CREATED)
async def evaluate_model_endpoint(
    payload: FineTuningEvaluateRequest, model_ctx: tuple[FineTunedModel, OrganizationMember] = Depends(require_model_admin), db: AsyncSession = Depends(get_db),
):
    """Real, synchronous evaluation for a real, typically small
    evaluation dataset -- `evaluate_fine_tuned_model` (Celery) is
    available separately for a real, large one a caller doesn't want
    to wait on inline."""
    model, _caller = model_ctx
    try:
        evaluation = await fine_tuning_service.evaluate_model(db, model.id, payload.dataset_id, None)
    except fine_tuning_service.FineTuningNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(evaluation)
    return evaluation


@router.get("/fine-tuning/models/{model_id}/evaluations", response_model=list[FineTuningEvaluationResponse])
async def list_evaluations_endpoint(model_ctx: tuple[FineTunedModel, OrganizationMember] = Depends(require_model_member), db: AsyncSession = Depends(get_db)):
    model, _caller = model_ctx
    return await fine_tuning_service.list_evaluations(db, model.id)
