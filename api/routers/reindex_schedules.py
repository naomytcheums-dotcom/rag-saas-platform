"""
Partie 2.2.15 -- managing an organization's own `ReindexSchedule`
rows. Two of these four endpoints are NOT org-scoped
(`/reindex-schedules/{schedule_id}`, this étape's own literal paths) --
same real shape as api/routers/external_sources.py's own
`/sources/{source_id}*`: look the schedule up FIRST, then check the
CALLER's own membership/role in ITS organization manually.

Every real write here is Admin+ (this étape's own literal ask, a real,
deliberate STRICTER tier than Partie 2.2.14's own Manager+ sources --
an automatic, organization-wide, recurring reindex is a bigger real
lever to hand out than a single sync connection).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.reindex_schedule import ReindexSchedule
from api.models.user import User
from api.schemas.reindex_schedules import ReindexScheduleCreateRequest, ReindexScheduleResponse, ReindexScheduleUpdateRequest
from api.security.permissions import require_permission
from api.security.organizations import require_org_admin
from api.security.reindex_schedules import create_reindex_schedule, delete_reindex_schedule, list_reindex_schedules, update_reindex_schedule

router = APIRouter(tags=["reindex-schedules"])


def _to_response(row: ReindexSchedule) -> ReindexScheduleResponse:
    return ReindexScheduleResponse(
        id=row.id, organization_id=row.organization_id, schedule_name=row.schedule_name, cron_pattern=row.cron_pattern,
        enabled=row.enabled, last_run_at=row.last_run_at, next_run_at=row.next_run_at, created_at=row.created_at, updated_at=row.updated_at,
    )


async def _get_schedule_and_membership(db: AsyncSession, schedule_id: uuid.UUID, current_user: User) -> tuple[ReindexSchedule, OrganizationMember]:
    """Same real anti-enumeration shape as
    api/routers/external_sources.py's own _get_source_and_membership."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    schedule = await db.get(ReindexSchedule, schedule_id)
    if schedule is None:
        raise not_found
    membership = await db.scalar(
        select(OrganizationMember).where(OrganizationMember.organization_id == schedule.organization_id, OrganizationMember.user_id == current_user.id)
    )
    if membership is None:
        raise not_found
    return schedule, membership


def _require_admin(membership: OrganizationMember) -> None:
    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin access required")


@router.post("/organizations/{org_id}/reindex-schedules", response_model=ReindexScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_reindex_schedule_route(
    org_id: uuid.UUID, payload: ReindexScheduleCreateRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:manage")), db: AsyncSession = Depends(get_db),
):
    try:
        schedule = await create_reindex_schedule(db, org_id, payload.schedule_name, payload.cron_pattern, payload.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await db.commit()
    await db.refresh(schedule)
    return _to_response(schedule)


@router.get("/organizations/{org_id}/reindex-schedules", response_model=list[ReindexScheduleResponse])
async def list_reindex_schedules_route(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("documents:manage")), db: AsyncSession = Depends(get_db),
):
    rows = await list_reindex_schedules(db, org_id)
    return [_to_response(row) for row in rows]


@router.patch("/reindex-schedules/{schedule_id}", response_model=ReindexScheduleResponse)
async def update_reindex_schedule_route(
    schedule_id: uuid.UUID, payload: ReindexScheduleUpdateRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    _schedule, membership = await _get_schedule_and_membership(db, schedule_id, current_user)
    _require_admin(membership)
    try:
        schedule = await update_reindex_schedule(db, schedule_id, schedule_name=payload.schedule_name, cron_pattern=payload.cron_pattern, enabled=payload.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await db.commit()
    await db.refresh(schedule)
    return _to_response(schedule)


@router.delete("/reindex-schedules/{schedule_id}")
async def delete_reindex_schedule_route(
    schedule_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    _schedule, membership = await _get_schedule_and_membership(db, schedule_id, current_user)
    _require_admin(membership)
    await delete_reindex_schedule(db, schedule_id)
    await db.commit()
    return {"message": "Reindex schedule deleted"}
