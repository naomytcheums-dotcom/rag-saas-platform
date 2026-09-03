"""
Partie 1.4.6 -- viewing and toggling an organization's white-label
setting. Both endpoints are Owner-only, same boundary as branding's own
PATCH (api/routers/organization_branding.py) -- unlike THAT endpoint's
GET (deliberately public, so a login screen/embeddable widget can fetch
branding before authentication), this one is an admin-facing
configuration view, not something a visitor needs.

The underlying data is identical to GET/PATCH .../branding (see
api/security/white_label.py's own docstring) -- this router exists so
white-label has its own stable, purpose-named endpoint rather than
requiring every caller to know it's "really" a branding field.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.schemas.white_label import WhiteLabelConfigResponse, WhiteLabelUpdateRequest
from api.security.organizations import require_org_owner
from api.security.white_label import get_white_label_config, update_white_label

router = APIRouter(tags=["white-label"])


@router.get("/organizations/{org_id}/white-label", response_model=WhiteLabelConfigResponse)
async def get_white_label_route(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    config = await get_white_label_config(db, org_id)
    return WhiteLabelConfigResponse(organization_id=org_id, **config)


@router.patch("/organizations/{org_id}/white-label", response_model=WhiteLabelConfigResponse)
async def update_white_label_route(
    org_id: uuid.UUID, payload: WhiteLabelUpdateRequest,
    _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True)
    if "hide_platform_branding" in updates:
        updated = await update_white_label(db, org_id, updates["hide_platform_branding"])
    else:
        updated = await get_white_label_config(db, org_id)
    await db.commit()
    return WhiteLabelConfigResponse(organization_id=org_id, **updated)
