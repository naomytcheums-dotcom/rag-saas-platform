"""Partie 7.3.9 -- regression threshold endpoints. Org-scoped routes
reuse `api/security/organizations.py`'s own `require_org_admin`
directly (they already carry a real `{org_id}` path param); single-
resource routes use this module's own new `require_regression_threshold_admin`."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.evaluation import RegressionThreshold
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.evaluation import (
    RegressionThresholdCheckRequest, RegressionThresholdCreateRequest, RegressionThresholdResponse,
    RegressionThresholdUpdateRequest, RegressionThresholdViolation,
)
from api.security.permissions import require_permission
from api.security.evaluation import require_regression_threshold_admin
from api.security.organizations import require_org_admin
from api.services.regression_thresholds import (
    check_regression_thresholds, delete_regression_threshold, get_regression_thresholds, set_regression_threshold,
    update_regression_threshold,
)

router = APIRouter(tags=["regression-thresholds"])


@router.post("/organizations/{org_id}/thresholds", response_model=RegressionThresholdResponse, status_code=status.HTTP_201_CREATED)
async def set_regression_threshold_endpoint(
    org_id: uuid.UUID, payload: RegressionThresholdCreateRequest, _caller: OrganizationMember = Depends(require_permission("evaluation:manage")),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    threshold = await set_regression_threshold(db, org_id, payload.metric, payload.threshold, payload.severity, current_user.id)
    await db.commit()
    await db.refresh(threshold)
    return threshold


@router.get("/organizations/{org_id}/thresholds", response_model=list[RegressionThresholdResponse])
async def list_regression_thresholds_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db)):
    return await get_regression_thresholds(db, org_id)


@router.get("/thresholds/{threshold_id}", response_model=RegressionThresholdResponse)
async def get_regression_threshold_endpoint(threshold_ctx: tuple[RegressionThreshold, OrganizationMember] = Depends(require_regression_threshold_admin)):
    threshold, _caller = threshold_ctx
    return threshold


@router.patch("/thresholds/{threshold_id}", response_model=RegressionThresholdResponse)
async def update_regression_threshold_endpoint(
    payload: RegressionThresholdUpdateRequest, threshold_ctx: tuple[RegressionThreshold, OrganizationMember] = Depends(require_regression_threshold_admin),
    db: AsyncSession = Depends(get_db),
):
    threshold, _caller = threshold_ctx
    updated = await update_regression_threshold(db, threshold.id, payload.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(updated)
    return updated


@router.delete("/thresholds/{threshold_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_regression_threshold_endpoint(
    threshold_ctx: tuple[RegressionThreshold, OrganizationMember] = Depends(require_regression_threshold_admin), db: AsyncSession = Depends(get_db),
):
    threshold, _caller = threshold_ctx
    await delete_regression_threshold(db, threshold.id)
    await db.commit()


@router.post("/organizations/{org_id}/thresholds/check", response_model=list[RegressionThresholdViolation])
async def check_regression_thresholds_endpoint(
    org_id: uuid.UUID, payload: RegressionThresholdCheckRequest, _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    return await check_regression_thresholds(db, org_id, payload.metrics)
