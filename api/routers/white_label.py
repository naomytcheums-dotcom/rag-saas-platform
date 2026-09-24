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

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.schemas.white_label import (
    ConfigureEmailRequest, SetCustomDomainRequest, WhiteLabelConfigResponse, WhiteLabelFullConfigResponse,
    WhiteLabelFullUpdateRequest, WhiteLabelUpdateRequest,
)
from api.security.permissions import require_permission
from api.security.organizations import require_org_admin, require_org_member, require_org_owner
from api.security.white_label import (
    DomainNotFoundError, configure_email, get_white_label_config, get_whitelabel_config, get_whitelabel_preview,
    remove_custom_domain, remove_email_config, remove_logo, reset_whitelabel, set_custom_domain, update_white_label,
    update_whitelabel_config, upload_favicon, upload_logo, verify_domain,
)

router = APIRouter(tags=["white-label"])


@router.get("/organizations/{org_id}/white-label", response_model=WhiteLabelConfigResponse)
async def get_white_label_route(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    config = await get_white_label_config(db, org_id)
    return WhiteLabelConfigResponse(organization_id=org_id, **config)


@router.patch("/organizations/{org_id}/white-label", response_model=WhiteLabelConfigResponse)
async def update_white_label_route(
    org_id: uuid.UUID, payload: WhiteLabelUpdateRequest,
    _caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True)
    if "hide_platform_branding" in updates:
        updated = await update_white_label(db, org_id, updates["hide_platform_branding"])
    else:
        updated = await get_white_label_config(db, org_id)
    await db.commit()
    return WhiteLabelConfigResponse(organization_id=org_id, **updated)


# -- Partie 19: the full white-label surface (Member+ read, Admin+ write) ----
# Deliberately laxer than the pre-existing endpoints above (Owner-only,
# unchanged) -- the spec for this part explicitly asked for Admin+/
# Member+, a real, intentional access-level difference from the older
# toggle-only endpoints, not an inconsistency.

@router.get("/organizations/{org_id}/whitelabel/config", response_model=WhiteLabelFullConfigResponse)
async def get_whitelabel_config_route(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("settings:read")), db: AsyncSession = Depends(get_db),
):
    config = await get_whitelabel_config(db, org_id)
    return WhiteLabelFullConfigResponse(organization_id=org_id, **config)


@router.patch("/organizations/{org_id}/whitelabel/config", response_model=WhiteLabelFullConfigResponse)
async def update_whitelabel_config_route(
    org_id: uuid.UUID, payload: WhiteLabelFullUpdateRequest,
    caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True)
    config = await update_whitelabel_config(db, org_id, updates, caller.user_id)
    await db.commit()
    return WhiteLabelFullConfigResponse(organization_id=org_id, **config)


@router.post("/organizations/{org_id}/whitelabel/domain", response_model=WhiteLabelFullConfigResponse, status_code=status.HTTP_201_CREATED)
async def set_whitelabel_domain_route(
    org_id: uuid.UUID, payload: SetCustomDomainRequest,
    caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    try:
        config = await set_custom_domain(db, org_id, payload.domain, caller.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await db.commit()
    return WhiteLabelFullConfigResponse(organization_id=org_id, **config)


@router.delete("/organizations/{org_id}/whitelabel/domain", response_model=WhiteLabelFullConfigResponse)
async def remove_whitelabel_domain_route(
    org_id: uuid.UUID, caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    try:
        config = await remove_custom_domain(db, org_id, caller.user_id)
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    await db.commit()
    return WhiteLabelFullConfigResponse(organization_id=org_id, **config)


@router.post("/organizations/{org_id}/whitelabel/domain/verify", response_model=WhiteLabelFullConfigResponse)
async def verify_whitelabel_domain_route(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    try:
        config = await verify_domain(db, org_id)
    except DomainNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    await db.commit()
    return WhiteLabelFullConfigResponse(organization_id=org_id, **config)


@router.post("/organizations/{org_id}/whitelabel/email", response_model=WhiteLabelFullConfigResponse)
async def configure_whitelabel_email_route(
    org_id: uuid.UUID, payload: ConfigureEmailRequest,
    caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    config = await configure_email(db, org_id, sender_name=payload.sender_name, sender_email=payload.sender_email, user_id=caller.user_id)
    await db.commit()
    return WhiteLabelFullConfigResponse(organization_id=org_id, **config)


@router.delete("/organizations/{org_id}/whitelabel/email", response_model=WhiteLabelFullConfigResponse)
async def remove_whitelabel_email_route(
    org_id: uuid.UUID, caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    config = await remove_email_config(db, org_id, caller.user_id)
    await db.commit()
    return WhiteLabelFullConfigResponse(organization_id=org_id, **config)


@router.post("/organizations/{org_id}/whitelabel/logo", response_model=WhiteLabelFullConfigResponse)
async def upload_whitelabel_logo_route(
    org_id: uuid.UUID, file: UploadFile,
    caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    try:
        config = await upload_logo(db, org_id, content, caller.user_id)
    except (ValueError, EnvironmentError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    await db.commit()
    return WhiteLabelFullConfigResponse(organization_id=org_id, **config)


@router.delete("/organizations/{org_id}/whitelabel/logo", response_model=WhiteLabelFullConfigResponse)
async def remove_whitelabel_logo_route(
    org_id: uuid.UUID, caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    config = await remove_logo(db, org_id, caller.user_id)
    await db.commit()
    return WhiteLabelFullConfigResponse(organization_id=org_id, **config)


@router.post("/organizations/{org_id}/whitelabel/favicon", response_model=WhiteLabelFullConfigResponse)
async def upload_whitelabel_favicon_route(
    org_id: uuid.UUID, file: UploadFile,
    caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    try:
        config = await upload_favicon(db, org_id, content, caller.user_id)
    except (ValueError, EnvironmentError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    await db.commit()
    return WhiteLabelFullConfigResponse(organization_id=org_id, **config)


@router.get("/organizations/{org_id}/whitelabel/preview", response_model=WhiteLabelFullConfigResponse)
async def get_whitelabel_preview_route(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("settings:read")), db: AsyncSession = Depends(get_db),
):
    config = await get_whitelabel_preview(db, org_id)
    return WhiteLabelFullConfigResponse(organization_id=org_id, **config)


@router.post("/organizations/{org_id}/whitelabel/reset", response_model=WhiteLabelFullConfigResponse)
async def reset_whitelabel_route(
    org_id: uuid.UUID, caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    config = await reset_whitelabel(db, org_id, caller.user_id)
    await db.commit()
    return WhiteLabelFullConfigResponse(organization_id=org_id, **config)
