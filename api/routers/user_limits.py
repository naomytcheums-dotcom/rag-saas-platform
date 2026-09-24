"""
Partie 1.3.7 -- viewing and adjusting a specific member's per-user
limits (api/models/organization.py's six new OrganizationMember
columns). GET/PATCH on a specific member are Admin+ -- same tier as
every other member-management endpoint in
api/routers/organization_members.py; PATCH additionally rejects
targeting the organization's Owner (reject_if_target_is_owner), same
"an Admin cannot restrict the one role above them" boundary already
applied to role-update and removal.

GET /users/me/limits is the one exception: any authenticated user, no
Admin+ gate at all -- it only ever returns the CALLER's own data, across
every organization they belong to.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.user_limits import MemberLimitsResponse, MyLimitsResponse, UserLimitsEntry, UserLimitsUpdateRequest, UserLimitsUsageEntry
from api.security.permissions import require_permission
from api.security.organizations import get_organization_member_or_404, reject_if_target_is_owner, require_org_admin
from api.security.user_limits import get_user_limits, get_user_usage

router = APIRouter(tags=["user-limits"])


def _to_limits_entry(limits: dict) -> UserLimitsEntry:
    return UserLimitsEntry(**limits)


def _to_usage_entry(usage: dict) -> UserLimitsUsageEntry:
    return UserLimitsUsageEntry(
        requests_per_day=usage["requests_per_day"], documents=usage["documents"], conversations=usage["conversations"],
    )


@router.get("/users/me/limits", response_model=MyLimitsResponse)
async def get_my_limits(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    memberships = (await db.scalars(
        select(OrganizationMember).where(OrganizationMember.user_id == current_user.id)
    )).all()
    items = []
    for membership in memberships:
        limits = await get_user_limits(db, current_user.id, membership.organization_id)
        usage = await get_user_usage(db, current_user.id, membership.organization_id)
        items.append(MemberLimitsResponse(
            organization_id=membership.organization_id, user_id=current_user.id,
            limits=_to_limits_entry(limits), usage=_to_usage_entry(usage),
        ))
    return MyLimitsResponse(items=items)


@router.get("/organizations/{org_id}/members/{user_id}/limits", response_model=MemberLimitsResponse)
async def get_member_limits(
    org_id: uuid.UUID, user_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db),
):
    await get_organization_member_or_404(db, org_id, user_id)  # 404 if user_id isn't a member of org_id
    limits = await get_user_limits(db, user_id, org_id)
    usage = await get_user_usage(db, user_id, org_id)
    return MemberLimitsResponse(organization_id=org_id, user_id=user_id, limits=_to_limits_entry(limits), usage=_to_usage_entry(usage))


@router.patch("/organizations/{org_id}/members/{user_id}/limits", response_model=MemberLimitsResponse)
async def update_member_limits(
    org_id: uuid.UUID, user_id: uuid.UUID, payload: UserLimitsUpdateRequest,
    _caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db),
):
    target_membership = await get_organization_member_or_404(db, org_id, user_id)
    reject_if_target_is_owner(target_membership, action="change the limits of")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(target_membership, field, value)
    await db.commit()

    limits = await get_user_limits(db, user_id, org_id)
    usage = await get_user_usage(db, user_id, org_id)
    return MemberLimitsResponse(organization_id=org_id, user_id=user_id, limits=_to_limits_entry(limits), usage=_to_usage_entry(usage))
