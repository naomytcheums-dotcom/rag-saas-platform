"""
Partie 7.1.6 -- real benchmark-version endpoints. `POST/GET
/datasets/{dataset_id}/versions*` reuse `require_dataset_admin`
(Partie 7.1.1); `GET/POST /versions/...` resolve the real version
itself AND the caller's real Admin+ role together
(`api/security/evaluation.py`'s own `require_benchmark_version_admin`)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.evaluation import BenchmarkVersion, EvaluationDataset
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.evaluation import (
    BenchmarkVersionCompareResponse, BenchmarkVersionCreateRequest, BenchmarkVersionListResponse,
    BenchmarkVersionResponse, DatasetResponse, RollbackRequest,
)
from api.security.evaluation import require_benchmark_version_admin, require_dataset_admin
from api.services.benchmark_versions import (
    compare_benchmark_versions, create_benchmark_version, list_benchmark_versions, rollback_to_version,
)

router = APIRouter(tags=["benchmark-versions"])


@router.post("/datasets/{dataset_id}/versions", response_model=BenchmarkVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_benchmark_version_endpoint(
    payload: BenchmarkVersionCreateRequest, current_user: User = Depends(get_current_user),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    version = await create_benchmark_version(db, dataset.id, payload.description, payload.question_set_id, current_user.id)
    await db.commit()
    return version


@router.get("/datasets/{dataset_id}/versions", response_model=BenchmarkVersionListResponse)
async def list_benchmark_versions_endpoint(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await list_benchmark_versions(db, dataset.id, limit, offset)


@router.get("/versions/{version_id}", response_model=BenchmarkVersionResponse)
async def get_benchmark_version_endpoint(
    version_ctx: tuple[BenchmarkVersion, OrganizationMember] = Depends(require_benchmark_version_admin),
):
    version, _caller = version_ctx
    return version


@router.post("/versions/{version_id}/compare/{other_version_id}", response_model=BenchmarkVersionCompareResponse)
async def compare_benchmark_versions_endpoint(
    other_version_id: uuid.UUID, version_ctx: tuple[BenchmarkVersion, OrganizationMember] = Depends(require_benchmark_version_admin),
    db: AsyncSession = Depends(get_db),
):
    version, _caller = version_ctx
    try:
        return await compare_benchmark_versions(db, version.id, other_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/datasets/{dataset_id}/versions/rollback", response_model=DatasetResponse)
async def rollback_to_version_endpoint(
    payload: RollbackRequest, dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin),
    db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    try:
        restored = await rollback_to_version(db, dataset.id, payload.version_number)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if restored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown benchmark version")
    await db.commit()
    return restored
