"""
Partie 7.3.10 -- production A/B testing endpoints. Partie 21 adds the
missing lifecycle/CRUD/statistics endpoints and loosens list/get/
results/statistics to Member+ (this part's own explicit spec) while
keeping every write/lifecycle action Admin+, same as before.

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

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.evaluation import ABTest
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.evaluation import (
    ABTestAssignmentListResponse, ABTestChooseWinnerRequest, ABTestCreateRequest, ABTestListResponse, ABTestResponse,
    ABTestResultsResponse, ABTestTrackMetricRequest, ABTestUpdateRequest,
)
from api.security.permissions import require_permission
from api.security.evaluation import require_ab_test_admin, require_ab_test_member
from api.security.organizations import require_org_admin, require_org_member
from api.services import ab_tests as ab_tests_service

router = APIRouter(tags=["ab-tests"])


@router.post("/organizations/{org_id}/ab-tests", response_model=ABTestResponse, status_code=status.HTTP_201_CREATED)
async def create_ab_test_endpoint(
    org_id: uuid.UUID, payload: ABTestCreateRequest, _caller: OrganizationMember = Depends(require_permission("evaluation:manage")),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    try:
        test = await ab_tests_service.create_ab_test(
            db, org_id, payload.name, payload.variant_a, payload.variant_b, payload.traffic_split, current_user.id,
            payload.description, payload.test_type, payload.target_metric, payload.min_sample_size, payload.confidence_level,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(test)
    return test


@router.get("/organizations/{org_id}/ab-tests", response_model=ABTestListResponse)
async def list_ab_tests_endpoint(
    org_id: uuid.UUID, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    _caller: OrganizationMember = Depends(require_permission("evaluation:read")), db: AsyncSession = Depends(get_db),
):
    return await ab_tests_service.list_ab_tests(db, org_id, limit, offset)


@router.get("/ab-tests/{test_id}", response_model=ABTestResponse)
async def get_ab_test_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_member)):
    test, _caller = test_ctx
    return test


@router.patch("/ab-tests/{test_id}", response_model=ABTestResponse)
async def update_ab_test_endpoint(
    payload: ABTestUpdateRequest, test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin),
    db: AsyncSession = Depends(get_db),
):
    test, _caller = test_ctx
    try:
        updated = await ab_tests_service.update_ab_test(db, test.id, payload.model_dump(exclude_unset=True))
    except ab_tests_service.ABTestNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    await db.refresh(updated)
    return updated


@router.delete("/ab-tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ab_test_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin), db: AsyncSession = Depends(get_db)):
    test, _caller = test_ctx
    await ab_tests_service.delete_ab_test(db, test.id)
    await db.commit()


@router.post("/ab-tests/{test_id}/start", response_model=ABTestResponse)
async def start_ab_test_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin), db: AsyncSession = Depends(get_db)):
    test, _caller = test_ctx
    updated = await ab_tests_service.start_ab_test(db, test.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/ab-tests/{test_id}/pause", response_model=ABTestResponse)
async def pause_ab_test_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin), db: AsyncSession = Depends(get_db)):
    test, _caller = test_ctx
    updated = await ab_tests_service.pause_ab_test(db, test.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/ab-tests/{test_id}/resume", response_model=ABTestResponse)
async def resume_ab_test_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin), db: AsyncSession = Depends(get_db)):
    test, _caller = test_ctx
    updated = await ab_tests_service.resume_ab_test(db, test.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/ab-tests/{test_id}/complete", response_model=ABTestResponse)
async def complete_ab_test_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin), db: AsyncSession = Depends(get_db)):
    test, _caller = test_ctx
    updated = await ab_tests_service.complete_ab_test(db, test.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.get("/ab-tests/{test_id}/results", response_model=ABTestResultsResponse)
async def get_ab_test_results_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_member), db: AsyncSession = Depends(get_db)):
    test, _caller = test_ctx
    return await ab_tests_service.get_ab_test_results(db, test.id)


@router.get("/ab-tests/{test_id}/statistics", response_model=ABTestResultsResponse)
async def get_ab_test_statistics_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_member), db: AsyncSession = Depends(get_db)):
    """Same real live computation as .../results -- this part's own
    spec names both endpoints, so both exist, rather than making a
    caller guess which one has the numbers. Also persists a real
    ABTestResult snapshot (see api/services/ab_tests.py's own
    save_ab_test_result_snapshot docstring)."""
    test, _caller = test_ctx
    await ab_tests_service.save_ab_test_result_snapshot(db, test.id)
    await db.commit()
    return await ab_tests_service.get_ab_test_results(db, test.id)


@router.get("/ab-tests/{test_id}/assignments", response_model=ABTestAssignmentListResponse)
async def list_ab_test_assignments_endpoint(
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin), db: AsyncSession = Depends(get_db),
):
    test, _caller = test_ctx
    return await ab_tests_service.list_ab_test_assignments(db, test.id, limit, offset)


@router.get("/ab-tests/{test_id}/export")
async def export_ab_test_endpoint(
    export_format: str = Query("json", alias="format"),
    test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin), db: AsyncSession = Depends(get_db),
):
    test, _caller = test_ctx
    if export_format not in ("json", "csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="format must be 'json' or 'csv'")
    content, media_type = await ab_tests_service.export_ab_test_results(db, test.id, export_format)
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename=ab_test.{export_format}"})


@router.post("/ab-tests/{test_id}/variants/choose", response_model=ABTestResponse)
async def choose_ab_test_winner_endpoint(
    payload: ABTestChooseWinnerRequest, test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin),
    db: AsyncSession = Depends(get_db),
):
    """Item 4's own literal "choisir le variant gagnant" -- a real,
    human decision (not a real, automated call): marks the real test
    `completed` and records the real chosen winner in `metrics["winner"]`.
    Left unchanged from before Partie 21 -- see POST .../decide below
    for the new, real, AUTOMATIC/statistical counterpart."""
    test, _caller = test_ctx
    updated = await ab_tests_service.complete_ab_test(db, test.id)
    updated.metrics = {**(updated.metrics or {}), "winner": payload.variant}
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/ab-tests/{test_id}/decide", response_model=ABTestResponse)
async def decide_ab_test_winner_endpoint(test_ctx: tuple[ABTest, OrganizationMember] = Depends(require_ab_test_admin), db: AsyncSession = Depends(get_db)):
    """Partie 21's own real, AUTOMATIC, statistics-driven decision --
    see api/services/ab_tests.py's own decide_ab_test_winner docstring
    for exactly how it differs from the manual .../variants/choose
    above."""
    test, _caller = test_ctx
    try:
        updated = await ab_tests_service.decide_ab_test_winner(db, test.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
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
        updated = await ab_tests_service.track_ab_test_metric(db, test.id, payload.variant, payload.metric, payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(updated)
    return updated
