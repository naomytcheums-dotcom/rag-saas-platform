"""
Partie 16 (ter) -- plugin marketplace.

`marketplace_router` (flat, no org prefix) is the real public catalog
(browse/search approved plugins, read reviews) -- discovering plugins
is not an org-scoped action. `org_router` covers everything that IS
org-scoped: publishing a plugin (as this org, the publisher),
installing/uninstalling one (into this org, the installer -- the SAME
organization can be both publisher and installer of its own plugin,
nothing here prevents that), and leaving a review (a real member of
THIS org, on behalf of it). `admin_router` is superadmin-only
moderation (approve/reject/suspend), same convention as
api/routers/sales.py's own platform-level `router`.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_superadmin
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.plugins import (
    InstallationResponse, InstallationUpdateRequest, PermissionResponse, PluginRejectRequest, PluginResponse,
    RatingSummaryResponse, ReviewRequest, ReviewResponse,
)
from api.security.organizations import require_org_admin, require_org_member
from api.security.plugin_manifest import ALLOWED_PLUGIN_PERMISSIONS, PluginCodeSecurityError, PluginManifestError
from api.services import plugins

marketplace_router = APIRouter(prefix="/marketplace", tags=["Plugin marketplace"])
org_router = APIRouter(prefix="/organizations/{org_id}/plugins", tags=["Plugin marketplace"])
admin_router = APIRouter(prefix="/admin/plugins", tags=["Plugin marketplace"])


async def _read_manifest(manifest_file: UploadFile) -> dict:
    import json

    raw = await manifest_file.read()
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="manifest.json is not valid JSON")


# -- Public marketplace catalog ------------------------------------------------

@marketplace_router.get("/permissions", response_model=list[PermissionResponse])
async def list_plugin_permissions_endpoint():
    return ALLOWED_PLUGIN_PERMISSIONS


@marketplace_router.get("/plugins", response_model=list[PluginResponse])
async def list_marketplace_plugins_endpoint(search: str | None = None, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)):
    return await plugins.list_marketplace_plugins(db, search=search, limit=limit, offset=offset)


@marketplace_router.get("/plugins/{plugin_id}", response_model=PluginResponse)
async def get_marketplace_plugin_endpoint(plugin_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        return await plugins.get_plugin(db, plugin_id)
    except plugins.PluginNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")


@marketplace_router.get("/plugins/{plugin_id}/rating", response_model=RatingSummaryResponse)
async def get_plugin_rating_endpoint(plugin_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await plugins.get_rating_summary(db, plugin_id)


@marketplace_router.get("/plugins/{plugin_id}/reviews", response_model=list[ReviewResponse])
async def list_plugin_reviews_endpoint(plugin_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await plugins.list_reviews(db, plugin_id)


# -- Publishing (org-scoped, admin) --------------------------------------------

@org_router.post("/publish", response_model=PluginResponse, status_code=status.HTTP_201_CREATED)
async def publish_plugin_endpoint(
    org_id: uuid.UUID, name: str = Form(...), description: str = Form(...),
    manifest: UploadFile = File(...), code: UploadFile = File(...),
    caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    manifest_data = await _read_manifest(manifest)
    code_bytes = await code.read()
    try:
        plugin = await plugins.publish_plugin(db, org_id, name=name, description=description, manifest=manifest_data, code=code_bytes, user_id=caller.user_id)
    except (PluginManifestError, PluginCodeSecurityError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except plugins.PluginStorageNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    await db.commit()
    return plugin


@org_router.put("/{plugin_id}", response_model=PluginResponse)
async def republish_plugin_endpoint(
    org_id: uuid.UUID, plugin_id: uuid.UUID, manifest: UploadFile = File(...), code: UploadFile = File(...), description: str | None = Form(None),
    _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    manifest_data = await _read_manifest(manifest)
    code_bytes = await code.read()
    try:
        plugin = await plugins.republish_plugin(db, org_id, plugin_id, description=description, manifest=manifest_data, code=code_bytes)
    except plugins.PluginNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    except (PluginManifestError, PluginCodeSecurityError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except plugins.PluginStorageNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    await db.commit()
    await db.refresh(plugin)
    return plugin


@org_router.get("/published", response_model=list[PluginResponse])
async def list_published_plugins_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await plugins.list_org_plugins(db, org_id)


@org_router.delete("/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plugin_endpoint(org_id: uuid.UUID, plugin_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        await plugins.delete_plugin(db, org_id, plugin_id)
    except plugins.PluginNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    await db.commit()


# -- Installation (org-scoped) -------------------------------------------------

@org_router.post("/{plugin_id}/install", response_model=InstallationResponse, status_code=status.HTTP_201_CREATED)
async def install_plugin_endpoint(org_id: uuid.UUID, plugin_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        installation = await plugins.install_plugin(db, org_id, plugin_id, caller.user_id)
    except plugins.PluginNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    except plugins.NotApprovedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except plugins.AlreadyInstalledError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This plugin is already installed for this organization")
    await db.commit()
    await db.refresh(installation)
    return installation


@org_router.get("/installed", response_model=list[InstallationResponse])
async def list_installed_plugins_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await plugins.list_installed_plugins(db, org_id)


@org_router.patch("/installed/{installation_id}", response_model=InstallationResponse)
async def update_installation_endpoint(org_id: uuid.UUID, installation_id: uuid.UUID, body: InstallationUpdateRequest, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        installation = await plugins.set_installation_enabled(db, org_id, installation_id, enabled=body.enabled, config=body.config)
    except plugins.InstallationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Installation not found")
    await db.commit()
    await db.refresh(installation)
    return installation


@org_router.delete("/installed/{installation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_plugin_endpoint(org_id: uuid.UUID, installation_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        await plugins.uninstall_plugin(db, org_id, installation_id)
    except plugins.InstallationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Installation not found")
    await db.commit()


# -- Reviews (org-scoped member) -----------------------------------------------

@org_router.post("/{plugin_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def submit_review_endpoint(org_id: uuid.UUID, plugin_id: uuid.UUID, body: ReviewRequest, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        review = await plugins.submit_review(db, plugin_id, org_id, caller.user_id, rating=body.rating, comment=body.comment)
    except plugins.PluginNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    except PluginManifestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await db.commit()
    await db.refresh(review)
    return review


# -- Admin moderation -----------------------------------------------------------

@admin_router.get("/pending", response_model=list[PluginResponse])
async def list_pending_plugins_endpoint(_admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    return await plugins.list_pending_plugins(db)


@admin_router.post("/{plugin_id}/approve", response_model=PluginResponse)
async def approve_plugin_endpoint(plugin_id: uuid.UUID, _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    try:
        plugin = await plugins.approve_plugin(db, plugin_id)
    except plugins.PluginNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    await db.commit()
    await db.refresh(plugin)
    return plugin


@admin_router.post("/{plugin_id}/reject", response_model=PluginResponse)
async def reject_plugin_endpoint(plugin_id: uuid.UUID, body: PluginRejectRequest, _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    try:
        plugin = await plugins.reject_plugin(db, plugin_id, reason=body.reason)
    except plugins.PluginNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    await db.commit()
    await db.refresh(plugin)
    return plugin


@admin_router.post("/{plugin_id}/suspend", response_model=PluginResponse)
async def suspend_plugin_endpoint(plugin_id: uuid.UUID, body: PluginRejectRequest, _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    try:
        plugin = await plugins.suspend_plugin(db, plugin_id, reason=body.reason)
    except plugins.PluginNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    await db.commit()
    await db.refresh(plugin)
    return plugin
