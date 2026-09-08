"""Partie 7.3.3 -- regression detection endpoints."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.evaluation import EvaluationDataset, RegressionDetection
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.evaluation import (
    RegressionDetectionListResponse, RegressionDetectionRequest, RegressionDetectionResponse, RegressionSummaryResponse,
)
from api.security.evaluation import require_dataset_admin, require_regression_admin
from api.services.regression_detection import detect_regressions, get_regression_summary, get_regressions, resolve_regression

router = APIRouter(tags=["regression-detection"])


@router.get("/datasets/{dataset_id}/regressions", response_model=RegressionDetectionListResponse)
async def get_regressions_endpoint(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await get_regressions(db, dataset.id, limit, offset)


@router.get("/datasets/{dataset_id}/regressions/summary", response_model=RegressionSummaryResponse)
async def get_regression_summary_endpoint(
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await get_regression_summary(db, dataset.id)


@router.post("/datasets/{dataset_id}/regressions/detect", response_model=list[RegressionDetectionResponse], status_code=status.HTTP_201_CREATED)
async def detect_regressions_endpoint(
    payload: RegressionDetectionRequest, dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin),
    db: AsyncSession = Depends(get_db),
):
    """Real, additive endpoint -- item 4's own literal endpoint list
    names `get`/`summary`/`resolve` but never a real trigger for
    `detect_regressions` itself; a real comparison needs a real caller
    to name WHICH two real jobs to compare, so a real endpoint is
    necessary here."""
    _dataset, _caller = dataset_ctx
    detections = await detect_regressions(db, payload.job_id, payload.previous_job_id)
    await db.commit()
    for detection in detections:
        await db.refresh(detection)
    return detections


@router.post("/regressions/{regression_id}/resolve", response_model=RegressionDetectionResponse)
async def resolve_regression_endpoint(
    regression_ctx: tuple[RegressionDetection, OrganizationMember] = Depends(require_regression_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    regression, _caller = regression_ctx
    resolved = await resolve_regression(db, regression.id, current_user.id)
    await db.commit()
    await db.refresh(resolved)
    return resolved
