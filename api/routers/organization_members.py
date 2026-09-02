"""
Etape 1.2.3 -- Admin: member-management endpoints, gated by
require_org_admin (Owner or Admin) rather than require_org_owner, since
this step's whole point is giving Admins real capabilities of their own
(inviting/promoting/demoting/removing members) without needing the
Owner for every one of them. Renaming/deleting the organization itself
(api/routers/organizations.py) stays Owner-only -- unaffected by this
step.

What Admin can NOT do, enforced here: change an Owner's role, or remove
an Owner (api/security/organizations.py's reject_if_target_is_owner --
applied regardless of caller, not just for Admins, see that function's
own docstring for why it's stricter than the letter of the spec).

Workspace management and organization-settings management (the other
two Admin capabilities named in this step's spec) have no endpoints
here because neither `workspaces` (Partie 1.3.2) nor
`organization_settings` (Partie 1.3.9) exist yet -- once they do, they
should reuse require_org_admin the same way these do, not invent a
separate permission check.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.audit_log import AuditAction
from api.models.organization import Organization, OrganizationMember
from api.models.user import User
from api.schemas.organizations import (
    OrganizationMemberEntry,
    OrganizationMemberInviteRequest,
    OrganizationMemberListResponse,
    OrganizationMemberRoleUpdateRequest,
)
from api.security.audit_log import log_audit_action
from api.security.organizations import get_organization_member_or_404, reject_if_target_is_owner, require_org_admin
from api.services.email import (
    send_organization_member_added_email,
    send_organization_member_removed_email,
    send_organization_member_role_changed_email,
)
from api.utils import client_ip

router = APIRouter(prefix="/organizations/{org_id}/members", tags=["organizations"])
logger = logging.getLogger(__name__)


@router.get("", response_model=OrganizationMemberListResponse)
async def list_organization_members(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(OrganizationMember, User.email)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == org_id)
        .order_by(OrganizationMember.joined_at.asc())
    )).all()
    return OrganizationMemberListResponse(items=[
        OrganizationMemberEntry(user_id=m.user_id, email=email, role=m.role, invited_by=m.invited_by, joined_at=m.joined_at)
        for m, email in rows
    ])


@router.post("/invite", response_model=OrganizationMemberEntry, status_code=status.HTTP_201_CREATED)
async def invite_organization_member(
    org_id: uuid.UUID, payload: OrganizationMemberInviteRequest, request: Request,
    caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    """
    "Invite" here means immediately adding an EXISTING account -- see
    OrganizationMemberInviteRequest's own docstring for why (no
    email-based invitation link exists yet, item 1.3.4).
    """
    target_user = await db.scalar(select(User).where(User.email == payload.email))
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No account exists with that email -- they must register first",
        )

    already_a_member = await db.scalar(
        select(OrganizationMember.id).where(
            OrganizationMember.organization_id == org_id, OrganizationMember.user_id == target_user.id,
        )
    )
    if already_a_member is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This user is already a member of the organization")

    membership = OrganizationMember(
        organization_id=org_id, user_id=target_user.id, role=payload.role, invited_by=caller.user_id,
    )
    db.add(membership)
    await db.flush()

    organization = await db.get(Organization, org_id)
    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.ORGANIZATION_MEMBER_ADDED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={"organization_id": str(org_id), "target_user_id": str(target_user.id), "role": payload.role.value},
    )
    await db.commit()

    try:
        send_organization_member_added_email(target_user.email, organization.name, payload.role.value)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send member-added notification to %s: %s", target_user.email, exc)

    return OrganizationMemberEntry(
        user_id=target_user.id, email=target_user.email, role=membership.role,
        invited_by=membership.invited_by, joined_at=membership.joined_at,
    )


@router.patch("/{user_id}/role", response_model=OrganizationMemberEntry)
async def update_organization_member_role(
    org_id: uuid.UUID, user_id: uuid.UUID, payload: OrganizationMemberRoleUpdateRequest, request: Request,
    caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    target_membership = await get_organization_member_or_404(db, org_id, user_id)
    reject_if_target_is_owner(target_membership, action="change the role of")

    previous_role = target_membership.role
    target_membership.role = payload.role
    target_email = await db.scalar(select(User.email).where(User.id == user_id))

    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.ORGANIZATION_MEMBER_ROLE_CHANGED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={
            "organization_id": str(org_id), "target_user_id": str(user_id),
            "previous_role": previous_role.value, "new_role": payload.role.value,
        },
    )
    await db.commit()

    organization = await db.get(Organization, org_id)
    try:
        send_organization_member_role_changed_email(target_email, organization.name, payload.role.value)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send role-changed notification to %s: %s", target_email, exc)

    return OrganizationMemberEntry(
        user_id=user_id, email=target_email, role=target_membership.role,
        invited_by=target_membership.invited_by, joined_at=target_membership.joined_at,
    )


@router.delete("/{user_id}")
async def remove_organization_member(
    org_id: uuid.UUID, user_id: uuid.UUID, request: Request,
    caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    target_membership = await get_organization_member_or_404(db, org_id, user_id)
    reject_if_target_is_owner(target_membership, action="remove")

    target_email = await db.scalar(select(User.email).where(User.id == user_id))
    organization = await db.get(Organization, org_id)

    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.ORGANIZATION_MEMBER_REMOVED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={"organization_id": str(org_id), "target_user_id": str(user_id)},
    )
    await db.execute(delete(OrganizationMember).where(OrganizationMember.id == target_membership.id))
    await db.commit()

    try:
        send_organization_member_removed_email(target_email, organization.name)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send member-removed notification to %s: %s", target_email, exc)

    return {"message": "Member removed"}
