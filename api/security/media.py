"""Partie 22 -- real, single-resource access dependency for
`/media/{media_asset_id}/...` routes (a flat path, no `{org_id}` --
same real, deliberate access-level adaptation already documented for
Parties 19/20/21's own literal specs). Org-scoped list/upload routes
(`/organizations/{org_id}/media`) reuse `require_org_member`/
`require_org_admin` directly, same as every other org-scoped router in
this codebase."""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.media import MediaAsset
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _membership_for(organization_id: uuid.UUID, current_user: User, db: AsyncSession) -> OrganizationMember:
    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise _NOT_FOUND
    return membership


def _require_member_excluding_viewer(membership: OrganizationMember) -> OrganizationMember:
    if membership.role == OrganizationRole.viewer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This action is not available to Viewer members")
    return membership


def _require_admin(membership: OrganizationMember) -> OrganizationMember:
    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin access required")
    return membership


async def require_media_member(
    media_asset_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[MediaAsset, OrganizationMember]:
    asset = await db.get(MediaAsset, media_asset_id)
    if asset is None:
        raise _NOT_FOUND
    membership = await _membership_for(asset.organization_id, current_user, db)
    return asset, _require_member_excluding_viewer(membership)


async def require_media_admin(
    media_asset_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[MediaAsset, OrganizationMember]:
    asset = await db.get(MediaAsset, media_asset_id)
    if asset is None:
        raise _NOT_FOUND
    membership = await _membership_for(asset.organization_id, current_user, db)
    return asset, _require_admin(membership)
