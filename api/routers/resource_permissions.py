"""
Etape 1.2.8 -- management endpoints for granular resource_permissions:
grant/list/revoke (Admin+ of the organization that owns the resource),
plus a self-service "what do I have" listing.

_resolve_organization_id resolves which organization a (resource_type,
resource_id) pair belongs to -- only "workspace" and "organization" can
be resolved today, since those are the only two resource types with a
real table to look the organization up from (see
api/security/resource_permissions.py's own docstring on why the other
resource types this step's spec names -- document, conversation, agent,
knowledge_base -- aren't supported yet). Any other resource_type gets a
400, not a 404 -- it isn't that this SPECIFIC resource doesn't exist,
it's that the type itself has no supported context to check against,
true regardless of resource_id.
"""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.audit_log import AuditAction
from api.models.organization import Organization, OrganizationRole
from api.models.resource_permission import ResourcePermission
from api.models.user import User
from api.models.workspace import Workspace
from api.schemas.resource_permissions import (
    ResourcePermissionEntry,
    ResourcePermissionGrantRequest,
    ResourcePermissionListResponse,
)
from api.security.audit_log import log_audit_action
from api.security.organizations import get_user_org_role
from api.security.resource_permissions import (
    SUPPORTED_RESOURCE_ACTIONS,
    check_resource_permission,
    get_user_resource_permissions,
    grant_resource_permission,
    list_permissions_on_resource,
    revoke_resource_permission,
)
from api.utils import client_ip

router = APIRouter(tags=["resource-permissions"])


async def _resolve_organization_id(db: AsyncSession, resource_type: str, resource_id: uuid.UUID) -> uuid.UUID:
    if resource_type not in SUPPORTED_RESOURCE_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Resource type '{resource_type}' is not supported for granular permissions",
        )
    if resource_type == "organization":
        organization = await db.get(Organization, resource_id)
        if organization is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return organization.id
    workspace = await db.get(Workspace, resource_id)  # resource_type == "workspace", the only case left
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return workspace.organization_id


async def _require_org_admin_for_resource(
    db: AsyncSession, current_user: User, resource_type: str, resource_id: uuid.UUID,
) -> tuple[uuid.UUID, OrganizationRole]:
    """404 for both "no such resource" and "you're not an Admin+ member
    of its organization" -- same anti-enumeration shape used everywhere
    else in this codebase (api/security/organizations.py's
    require_org_member); a non-admin member doesn't get to learn "this
    resource DOES exist, you're just not allowed" via a 403 that a
    non-member of the org couldn't get either."""
    organization_id = await _resolve_organization_id(db, resource_type, resource_id)
    role = await get_user_org_role(db, current_user.id, organization_id)
    if role is None or role not in (OrganizationRole.owner, OrganizationRole.admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return organization_id, role


async def _caller_can_perform(
    db: AsyncSession, *, user_id: uuid.UUID, role: OrganizationRole, resource_type: str, resource_id: uuid.UUID, action: str,
) -> bool:
    """
    "Can the caller themselves currently do `action` on this resource?"
    -- checked before letting them GRANT that same action to someone
    else (this step's own explicit rule: a user cannot hand out access
    they don't have). Restates, for grant-time, exactly the same role
    semantics already enforced live elsewhere (require_org_manager/
    admin/owner in api/security/organizations.py, require_workspace_permission
    in api/security/workspaces.py) -- e.g. an Admin passes THIS
    endpoint's own Admin+ gate but does NOT have organization:delete
    (Owner-only, unchanged since Etape 1.2.2), so an Admin attempting to
    grant organization:delete is correctly refused here even though they
    cleared _require_org_admin_for_resource above.
    """
    if await check_resource_permission(db, user_id=user_id, resource_type=resource_type, resource_id=resource_id, action=action):
        return True
    if resource_type == "workspace":
        if action == "read":
            return True
        return role in (OrganizationRole.owner, OrganizationRole.admin, OrganizationRole.manager)
    if resource_type == "organization":
        if action == "read":
            return True
        if action == "manage_members":
            return role in (OrganizationRole.owner, OrganizationRole.admin)
        return role == OrganizationRole.owner  # update/delete -- Owner only, matches require_org_owner
    return False


def _to_entry(permission: ResourcePermission) -> ResourcePermissionEntry:
    now = dt.datetime.now(dt.timezone.utc)
    expires_at = permission.expires_at
    # SQLite (the fast test suite) round-trips DateTime(timezone=True)
    # values as naive, even though real Postgres returns them
    # timezone-aware -- comparing a naive value against `now` (aware)
    # raises TypeError. A naive value from either backend always means
    # "stored as UTC" in this codebase (every DateTime column here uses
    # server_default=func.now()/passed-in aware datetimes), so treating
    # it as UTC on read is correct, not a guess.
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=dt.timezone.utc)
    return ResourcePermissionEntry(
        id=permission.id, resource_type=permission.resource_type, resource_id=permission.resource_id,
        user_id=permission.user_id, action=permission.action, granted_by=permission.granted_by,
        granted_at=permission.granted_at, expires_at=permission.expires_at,
        is_expired=expires_at is not None and expires_at <= now,
    )


@router.get("/resources/{resource_type}/{resource_id}/permissions", response_model=ResourcePermissionListResponse)
async def list_resource_permissions(
    resource_type: str, resource_id: uuid.UUID,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _require_org_admin_for_resource(db, current_user, resource_type, resource_id)
    permissions = await list_permissions_on_resource(db, resource_type=resource_type, resource_id=resource_id)
    return ResourcePermissionListResponse(items=[_to_entry(p) for p in permissions])


@router.post(
    "/resources/{resource_type}/{resource_id}/permissions", response_model=ResourcePermissionEntry,
    status_code=status.HTTP_201_CREATED,
)
async def grant_permission(
    resource_type: str, resource_id: uuid.UUID, payload: ResourcePermissionGrantRequest, request: Request,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    organization_id, role = await _require_org_admin_for_resource(db, current_user, resource_type, resource_id)

    target_role = await get_user_org_role(db, payload.user_id, organization_id)
    if target_role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Target user is not a member of this organization",
        )

    if not await _caller_can_perform(
        db, user_id=current_user.id, role=role, resource_type=resource_type, resource_id=resource_id, action=payload.action,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot grant '{payload.action}' -- you do not have it yourself",
        )

    permission = await grant_resource_permission(
        db, user_id=payload.user_id, organization_id=organization_id, resource_type=resource_type, resource_id=resource_id,
        action=payload.action, granted_by=current_user.id, expires_at=payload.expires_at,
    )
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.RESOURCE_PERMISSION_GRANTED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={
            "organization_id": str(organization_id), "resource_type": resource_type, "resource_id": str(resource_id),
            "target_user_id": str(payload.user_id), "action": payload.action,
        },
    )
    await db.commit()
    await db.refresh(permission)
    return _to_entry(permission)


@router.delete("/resources/{resource_type}/{resource_id}/permissions/{user_id}/{action}")
async def revoke_permission(
    resource_type: str, resource_id: uuid.UUID, user_id: uuid.UUID, action: str, request: Request,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    organization_id, _role = await _require_org_admin_for_resource(db, current_user, resource_type, resource_id)

    existed = await revoke_resource_permission(db, user_id=user_id, resource_type=resource_type, resource_id=resource_id, action=action)
    if not existed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.RESOURCE_PERMISSION_REVOKED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={
            "organization_id": str(organization_id), "resource_type": resource_type, "resource_id": str(resource_id),
            "target_user_id": str(user_id), "action": action,
        },
    )
    await db.commit()
    return {"message": "Permission revoked"}


@router.get("/users/me/permissions", response_model=ResourcePermissionListResponse)
async def list_my_permissions(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    permissions = await get_user_resource_permissions(db, user_id=current_user.id)
    return ResourcePermissionListResponse(items=[_to_entry(p) for p in permissions])
