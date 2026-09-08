"""
Partie 7.3.4/7.3.5/7.3.6/7.3.7 -- model/retriever/reranker/prompt
comparison endpoints. All 4 literal path families route through the
SAME real, shared engine (`api/services/comparison_jobs.py`), and all
4 real `create_*` endpoints auto-schedule real Celery execution
immediately (satisfying every one of these 4 étapes' own real
"performance: exécutées de manière asynchrone" vision critique, even
though only 7.3.4's own literal endpoint list names an explicit
`POST /comparisons/{id}/run` -- kept here too, as a real, additional
way to (re-)trigger an existing real comparison, e.g. after a real,
transient Celery failure)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.evaluation import ComparisonJob, EvaluationDataset
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.evaluation import ComparisonJobCreateRequest, ComparisonJobListResponse, ComparisonJobResponse
from api.security.evaluation import require_comparison_admin, require_dataset_admin
from api.services.comparison_jobs import (
    create_model_comparison, create_prompt_comparison, create_reranker_comparison, create_retriever_comparison,
    get_comparison_results, list_model_comparisons, list_prompt_comparisons, list_reranker_comparisons,
    list_retriever_comparisons, schedule_comparison_job_processing,
)

router = APIRouter(tags=["comparison-jobs"])


async def _create(create_fn, dataset, payload, current_user, db) -> ComparisonJob:
    try:
        job = await create_fn(db, dataset.id, payload.name, payload.variants, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(job)
    schedule_comparison_job_processing(job.id)
    return job


# --------------------------------------- 7.3.4 -- Model comparison --

@router.post("/datasets/{dataset_id}/compare", response_model=ComparisonJobResponse, status_code=status.HTTP_201_CREATED)
async def create_model_comparison_endpoint(
    payload: ComparisonJobCreateRequest, dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await _create(create_model_comparison, dataset, payload, current_user, db)


@router.get("/datasets/{dataset_id}/comparisons", response_model=ComparisonJobListResponse)
async def list_model_comparisons_endpoint(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await list_model_comparisons(db, dataset.id, limit, offset)


@router.get("/comparisons/{comparison_id}", response_model=ComparisonJobResponse)
async def get_model_comparison_endpoint(comparison_ctx: tuple[ComparisonJob, OrganizationMember] = Depends(require_comparison_admin)):
    comparison, _caller = comparison_ctx
    return comparison


@router.get("/comparisons/{comparison_id}/results")
async def get_model_comparison_results_endpoint(
    comparison_ctx: tuple[ComparisonJob, OrganizationMember] = Depends(require_comparison_admin), db: AsyncSession = Depends(get_db),
):
    comparison, _caller = comparison_ctx
    return await get_comparison_results(db, comparison.id)


@router.post("/comparisons/{comparison_id}/run", response_model=ComparisonJobResponse)
async def run_model_comparison_endpoint(
    comparison_ctx: tuple[ComparisonJob, OrganizationMember] = Depends(require_comparison_admin), db: AsyncSession = Depends(get_db),
):
    comparison, _caller = comparison_ctx
    schedule_comparison_job_processing(comparison.id)
    return comparison


# --------------------------------------- 7.3.5 -- Retriever comparison --

@router.post("/datasets/{dataset_id}/retrievers/compare", response_model=ComparisonJobResponse, status_code=status.HTTP_201_CREATED)
async def create_retriever_comparison_endpoint(
    payload: ComparisonJobCreateRequest, dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await _create(create_retriever_comparison, dataset, payload, current_user, db)


@router.get("/datasets/{dataset_id}/retrievers/comparisons", response_model=ComparisonJobListResponse)
async def list_retriever_comparisons_endpoint(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await list_retriever_comparisons(db, dataset.id, limit, offset)


@router.get("/retriever-comparisons/{comparison_id}", response_model=ComparisonJobResponse)
async def get_retriever_comparison_endpoint(comparison_ctx: tuple[ComparisonJob, OrganizationMember] = Depends(require_comparison_admin)):
    comparison, _caller = comparison_ctx
    return comparison


@router.get("/retriever-comparisons/{comparison_id}/results")
async def get_retriever_comparison_results_endpoint(
    comparison_ctx: tuple[ComparisonJob, OrganizationMember] = Depends(require_comparison_admin), db: AsyncSession = Depends(get_db),
):
    comparison, _caller = comparison_ctx
    return await get_comparison_results(db, comparison.id)


# --------------------------------------- 7.3.6 -- Reranker comparison --

@router.post("/datasets/{dataset_id}/rerankers/compare", response_model=ComparisonJobResponse, status_code=status.HTTP_201_CREATED)
async def create_reranker_comparison_endpoint(
    payload: ComparisonJobCreateRequest, dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await _create(create_reranker_comparison, dataset, payload, current_user, db)


@router.get("/datasets/{dataset_id}/rerankers/comparisons", response_model=ComparisonJobListResponse)
async def list_reranker_comparisons_endpoint(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await list_reranker_comparisons(db, dataset.id, limit, offset)


@router.get("/reranker-comparisons/{comparison_id}", response_model=ComparisonJobResponse)
async def get_reranker_comparison_endpoint(comparison_ctx: tuple[ComparisonJob, OrganizationMember] = Depends(require_comparison_admin)):
    comparison, _caller = comparison_ctx
    return comparison


@router.get("/reranker-comparisons/{comparison_id}/results")
async def get_reranker_comparison_results_endpoint(
    comparison_ctx: tuple[ComparisonJob, OrganizationMember] = Depends(require_comparison_admin), db: AsyncSession = Depends(get_db),
):
    comparison, _caller = comparison_ctx
    return await get_comparison_results(db, comparison.id)


# --------------------------------------- 7.3.7 -- Prompt comparison --

@router.post("/datasets/{dataset_id}/prompts/compare", response_model=ComparisonJobResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_comparison_endpoint(
    payload: ComparisonJobCreateRequest, dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await _create(create_prompt_comparison, dataset, payload, current_user, db)


@router.get("/datasets/{dataset_id}/prompts/comparisons", response_model=ComparisonJobListResponse)
async def list_prompt_comparisons_endpoint(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await list_prompt_comparisons(db, dataset.id, limit, offset)


@router.get("/prompt-comparisons/{comparison_id}", response_model=ComparisonJobResponse)
async def get_prompt_comparison_endpoint(comparison_ctx: tuple[ComparisonJob, OrganizationMember] = Depends(require_comparison_admin)):
    comparison, _caller = comparison_ctx
    return comparison


@router.get("/prompt-comparisons/{comparison_id}/results")
async def get_prompt_comparison_results_endpoint(
    comparison_ctx: tuple[ComparisonJob, OrganizationMember] = Depends(require_comparison_admin), db: AsyncSession = Depends(get_db),
):
    comparison, _caller = comparison_ctx
    return await get_comparison_results(db, comparison.id)
