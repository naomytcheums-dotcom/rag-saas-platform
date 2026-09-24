"""Partie 7.3.1 -- automatic evaluation job endpoints. Every real route
resolves its own resource AND the caller's real Admin+ role together
(`api/security/evaluation.py`'s own `require_dataset_admin`/
`require_evaluation_job_admin`)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.evaluation import EvaluationDataset, EvaluationJob
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.evaluation import (
    EvaluationFailureCategoriesResponse, EvaluationFailureListResponse, EvaluationJobCreateRequest,
    EvaluationJobListResponse, EvaluationJobResponse, EvaluationResultListResponse,
)
from api.security.evaluation import require_dataset_admin, require_evaluation_job_admin
from api.services.evaluation_jobs import (
    cancel_evaluation_job, categorize_job_failures, create_evaluation_job, get_evaluation_job_results,
    get_job_failures, list_evaluation_jobs, schedule_evaluation_job_processing, compare_evaluation_jobs,
)

router = APIRouter(tags=["evaluation-jobs"])


@router.post("/datasets/{dataset_id}/evaluate", response_model=EvaluationJobResponse, status_code=status.HTTP_201_CREATED)
async def create_evaluation_job_endpoint(
    payload: EvaluationJobCreateRequest = EvaluationJobCreateRequest(),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    job = await create_evaluation_job(
        db, dataset.id, question_set_id=payload.question_set_id, agent_id=payload.agent_id,
        model_config=payload.model_config_override, created_by=current_user.id,
    )
    await db.commit()
    await db.refresh(job)
    schedule_evaluation_job_processing(job.id)
    return job


@router.get("/datasets/{dataset_id}/jobs", response_model=EvaluationJobListResponse)
async def list_evaluation_jobs_endpoint(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await list_evaluation_jobs(db, dataset.id, limit, offset)


@router.get("/jobs/{job_id}", response_model=EvaluationJobResponse)
async def get_evaluation_job_endpoint(job_ctx: tuple[EvaluationJob, OrganizationMember] = Depends(require_evaluation_job_admin)):
    job, _caller = job_ctx
    return job


@router.post("/jobs/{job_id}/cancel", response_model=EvaluationJobResponse)
async def cancel_evaluation_job_endpoint(
    job_ctx: tuple[EvaluationJob, OrganizationMember] = Depends(require_evaluation_job_admin), db: AsyncSession = Depends(get_db),
):
    job, _caller = job_ctx
    try:
        updated = await cancel_evaluation_job(db, job.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return updated


@router.get("/jobs/{job_id}/results", response_model=EvaluationResultListResponse)
async def get_evaluation_job_results_endpoint(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    job_ctx: tuple[EvaluationJob, OrganizationMember] = Depends(require_evaluation_job_admin), db: AsyncSession = Depends(get_db),
):
    job, _caller = job_ctx
    return await get_evaluation_job_results(db, job.id, limit, offset)


@router.get("/jobs/{job_id}/failures", response_model=EvaluationFailureListResponse)
async def get_evaluation_job_failures_endpoint(
    job_ctx: tuple[EvaluationJob, OrganizationMember] = Depends(require_evaluation_job_admin), db: AsyncSession = Depends(get_db),
):
    job, _caller = job_ctx
    failures = await get_job_failures(db, job.id)
    return {"items": failures, "total": len(failures)}


@router.get("/jobs/{job_id}/failures/categories", response_model=EvaluationFailureCategoriesResponse)
async def get_evaluation_job_failure_categories_endpoint(
    job_ctx: tuple[EvaluationJob, OrganizationMember] = Depends(require_evaluation_job_admin), db: AsyncSession = Depends(get_db),
):
    job, _caller = job_ctx
    return await categorize_job_failures(db, job.id)


@router.get("/jobs/{job_id}/comparison")
async def compare_evaluation_jobs_endpoint(
    job_id: uuid.UUID,
    with_job_id: uuid.UUID = Query(..., alias="with"),
    job_ctx: tuple[EvaluationJob, OrganizationMember] = Depends(require_evaluation_job_admin),
    db: AsyncSession = Depends(get_db),
):
    """Compare this job's own real, averaged metrics against another
    real job's own. Both jobs must belong to the same organization."""
    other_job = await db.get(EvaluationJob, with_job_id)
    if other_job is None or other_job.organization_id != job_ctx[0].organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    return await compare_evaluation_jobs(db, job_id, with_job_id)
