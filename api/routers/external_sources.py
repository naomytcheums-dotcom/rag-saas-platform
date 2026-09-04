"""
Partie 2.2.14 -- managing and triggering sync for an organization's own
`ExternalSource` connections. Two of these five endpoints are NOT
org-scoped (`/sources/{source_id}`[`/sync`], this étape's own literal
paths) -- same real shape as api/routers/documents.py's own
`/documents/{document_id}*`: look the source up FIRST, then check the
CALLER's own membership/role in ITS organization manually
(`_get_source_and_membership` below), same 404-for-non-member-or-
nonexistent anti-enumeration convention as `require_org_member` itself.

Every real write here (create/update/delete/sync) is Manager+ (this
étape's own literal ask) -- `require_org_manager` directly for the two
org-scoped routes (FastAPI resolves `org_id` automatically), the same
real role check applied by hand for the three that aren't.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.external_source import ExternalSource
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.schemas.external_sources import (
    ExternalSourceCreateRequest,
    ExternalSourceResponse,
    ExternalSourceSyncResponse,
    ExternalSourceUpdateRequest,
)
from api.security.external_sources import (
    create_external_source,
    delete_external_source,
    list_external_sources,
    sync_external_source,
    update_external_source,
)
from api.security.organizations import require_org_manager

router = APIRouter(tags=["external-sources"])


def _to_response(row: ExternalSource) -> ExternalSourceResponse:
    return ExternalSourceResponse(
        id=row.id, organization_id=row.organization_id, workspace_id=row.workspace_id, source_type=row.source_type,
        source_id=row.source_id, enabled=row.enabled, last_sync_at=row.last_sync_at, sync_status=row.sync_status,
        sync_error=row.sync_error, created_by=row.created_by, created_at=row.created_at, updated_at=row.updated_at,
    )


async def _get_source_and_membership(db: AsyncSession, source_id: uuid.UUID, current_user: User) -> tuple[ExternalSource, OrganizationMember]:
    """Shared by PATCH/DELETE/sync /sources/{source_id}* -- looks up
    the source, then the caller's membership in ITS organization. 404
    for both "no such source" and "you're not a member of the
    organization that owns it", the same anti-enumeration convention
    as api/routers/documents.py's own _get_document_and_membership."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    source = await db.get(ExternalSource, source_id)
    if source is None:
        raise not_found
    membership = await db.scalar(
        select(OrganizationMember).where(OrganizationMember.organization_id == source.organization_id, OrganizationMember.user_id == current_user.id)
    )
    if membership is None:
        raise not_found
    return source, membership


def _require_manager(membership: OrganizationMember) -> None:
    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin, OrganizationRole.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization manager access required")


@router.post("/organizations/{org_id}/sources", response_model=ExternalSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_external_source_route(
    org_id: uuid.UUID, payload: ExternalSourceCreateRequest,
    _caller: OrganizationMember = Depends(require_org_manager),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    try:
        source = await create_external_source(
            db, org_id, payload.workspace_id, payload.source_type, payload.source_id,
            payload.config, payload.enabled, current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await db.commit()
    await db.refresh(source)
    return _to_response(source)


@router.get("/organizations/{org_id}/sources", response_model=list[ExternalSourceResponse])
async def list_external_sources_route(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    rows = await list_external_sources(db, org_id)
    return [_to_response(row) for row in rows]


@router.patch("/sources/{source_id}", response_model=ExternalSourceResponse)
async def update_external_source_route(
    source_id: uuid.UUID, payload: ExternalSourceUpdateRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    _source, membership = await _get_source_and_membership(db, source_id, current_user)
    _require_manager(membership)
    source = await update_external_source(db, source_id, config=payload.config, enabled=payload.enabled, source_id_value=payload.source_id)
    await db.commit()
    await db.refresh(source)
    return _to_response(source)


@router.delete("/sources/{source_id}")
async def delete_external_source_route(
    source_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    _source, membership = await _get_source_and_membership(db, source_id, current_user)
    _require_manager(membership)
    await delete_external_source(db, source_id)
    await db.commit()
    return {"message": "External source deleted"}


@router.post("/sources/{source_id}/sync", response_model=ExternalSourceSyncResponse)
async def sync_external_source_route(
    source_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Item 4's own literal route -- Manager+, a real, single-source,
    synchronous sync (runs the real, unchanged import pipeline directly
    -- for a large container this blocks the request for as long as the
    real pipeline itself does; a caller wanting a fire-and-forget
    trigger instead should use the Celery-backed `sync_source_task`,
    the same real task the periodic sweep already uses)."""
    _source, membership = await _get_source_and_membership(db, source_id, current_user)
    _require_manager(membership)
    sync_status = await sync_external_source(db, source_id, current_user.id)
    await db.commit()
    return ExternalSourceSyncResponse(source_id=source_id, sync_status=sync_status)
