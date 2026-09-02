"""
Partie 1.3.10 -- viewing, adjusting, and uploading assets for an
organization's branding.

GET is deliberately PUBLIC -- the one exception in this entire codebase
to every other /organizations/{org_id}/... route requiring at least
require_org_member. Branding (logo, colors, name) exists to be shown on
a page a VISITOR reaches before they are a member of anything, or even
authenticated at all (a login screen, an embeddable widget) -- gating
it behind membership would defeat its own purpose. This deliberately
accepts a narrow tradeoff every other endpoint in this codebase avoids:
GET .../branding for ANY valid organization_id returns 200, revealing
that the id exists (weak enumeration) -- the anti-enumeration 404 every
require_org_member-gated route uses does not apply to something meant
to be public by design. Only a genuinely non-existent organization_id
gets a 404 here.

PATCH and the upload/delete endpoints are Owner-only, same boundary as
quotas' PATCH and settings' PATCH: changing what every visitor sees is
an organization-level decision, not a member-management one.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import Organization, OrganizationMember
from api.schemas.organization_branding import OrganizationBrandingResponse, OrganizationBrandingUpdateRequest
from api.security.organizations import require_org_owner
from api.security.organization_branding import get_org_branding, update_org_branding
from api.services.storage import delete_branding_asset, upload_organization_favicon, upload_organization_logo

router = APIRouter(tags=["organization-branding"])


@router.get("/organizations/{org_id}/branding", response_model=OrganizationBrandingResponse)
async def get_organization_branding(org_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    organization = await db.get(Organization, org_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    branding = await get_org_branding(db, org_id)
    return OrganizationBrandingResponse(organization_id=org_id, **branding)


@router.patch("/organizations/{org_id}/branding", response_model=OrganizationBrandingResponse)
async def update_organization_branding(
    org_id: uuid.UUID, payload: OrganizationBrandingUpdateRequest,
    _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True)
    updated = await update_org_branding(db, org_id, updates)
    await db.commit()
    return OrganizationBrandingResponse(organization_id=org_id, **updated)


@router.post("/organizations/{org_id}/branding/logo", response_model=OrganizationBrandingResponse)
async def upload_organization_logo_route(
    org_id: uuid.UUID, file: UploadFile,
    _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    """All actual validation (real image format, size, pixel dimensions)
    and the S3 call itself live in api/services/storage.py -- this route
    is just the HTTP plumbing around it, same split as
    api/routers/account.py's upload_avatar_route."""
    content = await file.read()
    try:
        url = upload_organization_logo(org_id, content)
    except (ValueError, EnvironmentError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    current = await get_org_branding(db, org_id)
    previous_logo_url = current["logo_url"]
    updated = await update_org_branding(db, org_id, {"logo_url": url})
    await db.commit()

    if previous_logo_url:
        delete_branding_asset(previous_logo_url)  # best-effort, never blocks the response

    return OrganizationBrandingResponse(organization_id=org_id, **updated)


@router.post("/organizations/{org_id}/branding/favicon", response_model=OrganizationBrandingResponse)
async def upload_organization_favicon_route(
    org_id: uuid.UUID, file: UploadFile,
    _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    try:
        url = upload_organization_favicon(org_id, content)
    except (ValueError, EnvironmentError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    current = await get_org_branding(db, org_id)
    previous_favicon_url = current["favicon_url"]
    updated = await update_org_branding(db, org_id, {"favicon_url": url})
    await db.commit()

    if previous_favicon_url:
        delete_branding_asset(previous_favicon_url)

    return OrganizationBrandingResponse(organization_id=org_id, **updated)


@router.delete("/organizations/{org_id}/branding/logo", response_model=OrganizationBrandingResponse)
async def delete_organization_logo(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    current = await get_org_branding(db, org_id)
    updated = await update_org_branding(db, org_id, {"logo_url": None})
    await db.commit()

    if current["logo_url"]:
        delete_branding_asset(current["logo_url"])

    return OrganizationBrandingResponse(organization_id=org_id, **updated)


@router.delete("/organizations/{org_id}/branding/favicon", response_model=OrganizationBrandingResponse)
async def delete_organization_favicon(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    current = await get_org_branding(db, org_id)
    updated = await update_org_branding(db, org_id, {"favicon_url": None})
    await db.commit()

    if current["favicon_url"]:
        delete_branding_asset(current["favicon_url"])

    return OrganizationBrandingResponse(organization_id=org_id, **updated)
