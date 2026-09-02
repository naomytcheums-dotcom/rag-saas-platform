"""
Partie 1.3.9 -- viewing and adjusting an organization's configuration.
GET is Admin+ (same tier as api/routers/quotas.py's GET -- an Admin
should be able to see how the organization is configured); PATCH is
Owner-only, same boundary as quotas' PATCH: changing what model/prompt/
retrieval strategy the whole organization uses is judged an
organization-level decision, not a member-management one.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.schemas.organization_settings import OrganizationSettingsResponse, OrganizationSettingsUpdateRequest
from api.security.organizations import require_org_admin, require_org_owner
from api.security.organization_settings import get_org_settings, update_org_settings

router = APIRouter(tags=["organization-settings"])


@router.get("/organizations/{org_id}/settings", response_model=OrganizationSettingsResponse)
async def get_organization_settings(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    settings = await get_org_settings(db, org_id)
    return OrganizationSettingsResponse(organization_id=org_id, **settings)


@router.patch("/organizations/{org_id}/settings", response_model=OrganizationSettingsResponse)
async def update_organization_settings(
    org_id: uuid.UUID, payload: OrganizationSettingsUpdateRequest,
    _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True)

    # Cross-field validation the per-field Field() bounds in
    # OrganizationSettingsUpdateRequest can't express on their own: a
    # PATCH may touch only one of the two (or neither), so it's checked
    # against the RESULTING effective pair, not the raw payload.
    current = await get_org_settings(db, org_id)
    merged_preview = {**current, **updates}
    if merged_preview["chunk_overlap"] >= merged_preview["chunk_size"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="chunk_overlap must be smaller than chunk_size",
        )

    updated = await update_org_settings(db, org_id, updates)
    await db.commit()
    return OrganizationSettingsResponse(organization_id=org_id, **updated)
