"""
Partie 7.3.10 -- production A/B testing endpoints. Admin+ throughout
(item 4's own literal ask).

**`get_ab_test_variant`, deliberately NOT its own endpoint**: it is a
real, fast, per-request BUCKETING function meant to be called directly
by real backend routing/serving code (e.g. inside a real generation
call, to pick which real variant config to use) -- gating it behind a
real, Admin+ HTTP round-trip would defeat its own real purpose.
Exposed here only via `POST /ab-tests/{id}/track` (real, additive --
the literal endpoint list names no route for `track_ab_test_metric`
either, despite listing it as its own literal function).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.evaluation import ABTest
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.evaluation import (
    ABTestChooseWinnerRequest, ABTestCreateRequest, ABTestListResponse, ABTestResponse, ABTestResultsResponse,
    ABTestTrackMetricRequest,
)
from api.security.evaluation import require_ab_test_admin
from api.security.organizations import require_org_admin
from api.services.ab_tests import (
    complete_ab_test, create_ab_test, get_ab_test_results, list_ab_tests, pause_ab_test, start_ab_test,
    track_ab_test_metric,
)

router = APIRouter(tags=["ab-tests"])


@router.post("/organizations/{org_id}/ab-tests", response_model=ABTestResponse, status_code=status.HTTP_201_CREATED)
async def create_ab_test_endpoint(
    org_id: uuid.UUID, payload: ABTestCreateRequest, _caller: OrganizationMember = Depends(require_org_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    try:
        test = await create_ab_test(
            db, org_id, payload.name, payload.variant_a, payload.variant_b, payload.traffic_split, current_user.id, payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(test)
    return test


@router.get("/organizations/{org_id}/ab-tests", response_model=ABTestListResponse)
async def list_ab_tests_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    return await list_ab_tests(db, org_id)


@router.get("/ab-tests/{test_id}", response_model=ABTestResponse)
async def get_ab_test_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin)):
    test, _caller = test_ctx
    return test


@router.post("/ab-tests/{test_id}/start", response_model=ABTestResponse)
async def start_ab_test_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin), db: AsyncSession = Depends(get_db)):
    test, _caller = test_ctx
    updated = await start_ab_test(db, test.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/ab-tests/{test_id}/pause", response_model=ABTestResponse)
async def pause_ab_test_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin), db: AsyncSession = Depends(get_db)):
    test, _caller = test_ctx
    updated = await pause_ab_test(db, test.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/ab-tests/{test_id}/complete", response_model=ABTestResponse)
async def complete_ab_test_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin), db: AsyncSession = Depends(get_db)):
    test, _caller = test_ctx
    updated = await complete_ab_test(db, test.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.get("/ab-tests/{test_id}/results", response_model=ABTestResultsResponse)
async def get_ab_test_results_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin), db: AsyncSession = Depends(get_db)):
    test, _caller = test_ctx
    return await get_ab_test_results(db, test.id)


@router.post("/ab-tests/{test_id}/variants/choose", response_model=ABTestResponse)
async def choose_ab_test_winner_endpoint(
    payload: ABTestChooseWinnerRequest, test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin),
    db: AsyncSession = Depends(get_db),
):
    """Item 4's own literal "choisir le variant gagnant" -- a real,
    human decision (not a real, automated call): marks the real test
    `completed` and records the real chosen winner in `metrics["winner"]`."""
    test, _caller = test_ctx
    updated = await complete_ab_test(db, test.id)
    updated.metrics = {**(updated.metrics or {}), "winner": payload.variant}
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/ab-tests/{test_id}/track", response_model=ABTestResponse)
async def track_ab_test_metric_endpoint(
    payload: ABTestTrackMetricRequest, test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin),
    db: AsyncSession = Depends(get_db),
):
    test, _caller = test_ctx
    try:
        updated = await track_ab_test_metric(db, test.id, payload.variant, payload.metric, payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(updated)
    return updated
