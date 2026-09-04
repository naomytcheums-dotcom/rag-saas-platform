"""
Partie 2.2.16 -- creating, listing, and controlling batch jobs. Three
of these five endpoints are NOT org-scoped (`/batch/jobs/{job_id}*`,
this étape's own literal paths) -- same real shape as
api/routers/external_sources.py's own `/sources/{source_id}*`: look
the job up FIRST, then check the CALLER's own membership/role in ITS
organization manually.

Every real endpoint here is Admin+ (this étape's own literal ask, a
real, deliberate acknowledgement that a batch job can itself run any
of Partie 2.2.8/2.2.9/2.2.14's own real destructive/administrative
actions -- delete, reindex, external sync -- across many real items at
once).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.batch_job import BatchJob, BatchJobItem
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.schemas.batch_jobs import BatchJobCreateRequest, BatchJobItemResponse, BatchJobResponse
import api.security.batch_jobs as batch_jobs_security
from api.security.batch_jobs import cancel_batch_job, create_batch_job, list_batch_job_items
from api.security.organizations import require_org_admin

router = APIRouter(tags=["batch-jobs"])


def _to_response(row: BatchJob) -> BatchJobResponse:
    return BatchJobResponse(
        id=row.id, organization_id=row.organization_id, job_type=row.job_type, status=row.status,
        total_items=row.total_items, processed_items=row.processed_items, failed_items=row.failed_items,
        created_by=row.created_by, created_at=row.created_at, started_at=row.started_at, completed_at=row.completed_at, error=row.error,
    )


def _item_to_response(row: BatchJobItem) -> BatchJobItemResponse:
    return BatchJobItemResponse(
        id=row.id, batch_job_id=row.batch_job_id, sequence=row.sequence, item_id=row.item_id,
        status=row.status, error=row.error, processed_at=row.processed_at,
    )


async def _get_job_and_membership(db: AsyncSession, job_id: uuid.UUID, current_user: User) -> tuple[BatchJob, OrganizationMember]:
    """Same real anti-enumeration shape as
    api/routers/external_sources.py's own _get_source_and_membership."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    job = await db.get(BatchJob, job_id)
    if job is None:
        raise not_found
    membership = await db.scalar(
        select(OrganizationMember).where(OrganizationMember.organization_id == job.organization_id, OrganizationMember.user_id == current_user.id)
    )
    if membership is None:
        raise not_found
    return job, membership


def _require_admin(membership: OrganizationMember) -> None:
    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin access required")


@router.post("/organizations/{org_id}/batch/jobs", response_model=BatchJobResponse, status_code=status.HTTP_201_CREATED)
async def create_batch_job_route(
    org_id: uuid.UUID, payload: BatchJobCreateRequest,
    _caller: OrganizationMember = Depends(require_org_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    try:
        job = await create_batch_job(db, org_id, payload.job_type, payload.items, payload.config, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await db.commit()
    await db.refresh(job)
    batch_jobs_security.schedule_batch_job_processing(job.id)
    return _to_response(job)


@router.get("/organizations/{org_id}/batch/jobs", response_model=list[BatchJobResponse])
async def list_batch_jobs_route(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    rows = (await db.scalars(
        select(BatchJob).where(BatchJob.organization_id == org_id).order_by(BatchJob.created_at.desc())
    )).all()
    return [_to_response(row) for row in rows]


@router.get("/batch/jobs/{job_id}", response_model=BatchJobResponse)
async def get_batch_job_route(
    job_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    job, membership = await _get_job_and_membership(db, job_id, current_user)
    _require_admin(membership)
    return _to_response(job)


@router.post("/batch/jobs/{job_id}/cancel", response_model=BatchJobResponse)
async def cancel_batch_job_route(
    job_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    _job, membership = await _get_job_and_membership(db, job_id, current_user)
    _require_admin(membership)
    try:
        job = await cancel_batch_job(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await db.commit()
    await db.refresh(job)
    return _to_response(job)


@router.get("/batch/jobs/{job_id}/items", response_model=list[BatchJobItemResponse])
async def list_batch_job_items_route(
    job_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    _job, membership = await _get_job_and_membership(db, job_id, current_user)
    _require_admin(membership)
    items = await list_batch_job_items(db, job_id)
    return [_item_to_response(item) for item in items]
