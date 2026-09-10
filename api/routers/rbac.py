"""
Partie 10.1 -- custom roles & granular permissions. Routes live under
`/organizations/{org_id}/rbac/...` (this codebase's real, established
multi-tenant convention -- see api/routers/webhooks.py's own docstring
on why a flat, org-less path would be incoherent with a user who can
belong to more than one organization), not the flat `/rbac/...` paths
Partie 10.1's own literal spec listed. `POST /rbac/check` is the one
exception kept flat, matching its schema (organization_id travels in
the request body instead of the path) since a permission check is
naturally asked "for this org, can I do X" rather than scoped by URL.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.rbac import (
    AssignPermissionsRequest,
    AssignRoleToUserRequest,
    CustomRoleCreateRequest,
    CustomRoleResponse,
    CustomRoleUpdateRequest,
    EffectivePermissionsResponse,
    PermissionCheckRequest,
    PermissionCheckResponse,
    PermissionResponse,
)
from api.security.organizations import get_organization_member_or_404, require_org_admin, require_org_member
from api.services.rbac_custom import (
    DuplicateRoleNameError,
    PermissionNotFoundError,
    RoleNotFoundError,
    assign_permissions_to_role,
    assign_role_to_user,
    check_permission,
    create_custom_role,
    delete_custom_role,
    get_custom_role_or_404,
    get_role_permission_keys,
    get_user_effective_permissions,
    list_custom_roles,
    list_permissions,
    remove_permission_from_role,
    remove_role_from_user,
    update_custom_role,
)

router = APIRouter(tags=["RBAC"])


async def _role_to_response(db: AsyncSession, role) -> CustomRoleResponse:
    return CustomRoleResponse(
        id=role.id, organization_id=role.organization_id, name=role.name, description=role.description,
        created_at=role.created_at, updated_at=role.updated_at,
        permission_keys=await get_role_permission_keys(db, role.id),
    )


@router.get("/organizations/{org_id}/rbac/permissions", response_model=list[PermissionResponse])
async def list_permissions_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    permissions = await list_permissions(db)
    # Real, necessary commit: list_permissions() may have just seeded the
    # 52-row catalog (ensure_permission_catalog_seeded's own flush-only
    # insert) -- without a commit here, api/database.py's get_db() closes
    # this session without ever persisting it, silently ROLLING BACK the
    # seed on every call. Found for real: the catalog kept coming back
    # empty on the very next request despite this endpoint appearing to
    # return 52 real rows.
    await db.commit()
    return [PermissionResponse.model_validate(p) for p in permissions]


@router.get("/organizations/{org_id}/rbac/roles", response_model=list[CustomRoleResponse])
async def list_roles_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    return [await _role_to_response(db, r) for r in await list_custom_roles(db, org_id)]


@router.post("/organizations/{org_id}/rbac/roles", response_model=CustomRoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role_endpoint(
    org_id: uuid.UUID, payload: CustomRoleCreateRequest,
    caller: OrganizationMember = Depends(require_org_admin), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    try:
        role = await create_custom_role(db, organization_id=org_id, name=payload.name, description=payload.description, user_id=current_user.id)
    except DuplicateRoleNameError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A role with this name already exists")
    await db.commit()
    return await _role_to_response(db, role)


@router.get("/organizations/{org_id}/rbac/roles/{role_id}", response_model=CustomRoleResponse)
async def get_role_endpoint(org_id: uuid.UUID, role_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        role = await get_custom_role_or_404(db, role_id, org_id)
    except RoleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return await _role_to_response(db, role)


@router.patch("/organizations/{org_id}/rbac/roles/{role_id}", response_model=CustomRoleResponse)
async def update_role_endpoint(
    org_id: uuid.UUID, role_id: uuid.UUID, payload: CustomRoleUpdateRequest,
    _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    try:
        role = await update_custom_role(db, role_id=role_id, organization_id=org_id, name=payload.name, description=payload.description)
    except RoleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    await db.refresh(role)  # updated_at is a server-side onupdate -- needs a real refresh after commit, same as api/routers/security_scan.py's own policy endpoints
    return await _role_to_response(db, role)


@router.delete("/organizations/{org_id}/rbac/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role_endpoint(org_id: uuid.UUID, role_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        await delete_custom_role(db, role_id=role_id, organization_id=org_id)
    except RoleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()


@router.post("/organizations/{org_id}/rbac/roles/{role_id}/permissions", response_model=CustomRoleResponse)
async def assign_permissions_endpoint(
    org_id: uuid.UUID, role_id: uuid.UUID, payload: AssignPermissionsRequest,
    _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    try:
        role = await assign_permissions_to_role(db, role_id=role_id, organization_id=org_id, permission_ids=payload.permission_ids)
    except RoleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    except PermissionNotFoundError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown permission id")
    await db.commit()
    return await _role_to_response(db, role)


@router.delete("/organizations/{org_id}/rbac/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_permission_endpoint(
    org_id: uuid.UUID, role_id: uuid.UUID, permission_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    try:
        await remove_permission_from_role(db, role_id=role_id, organization_id=org_id, permission_id=permission_id)
    except RoleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()


@router.post("/organizations/{org_id}/rbac/users/{user_id}/roles", status_code=status.HTTP_201_CREATED)
async def assign_role_to_user_endpoint(
    org_id: uuid.UUID, user_id: uuid.UUID, payload: AssignRoleToUserRequest,
    caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    await get_organization_member_or_404(db, org_id, user_id)
    try:
        await assign_role_to_user(db, user_id=user_id, role_id=payload.role_id, organization_id=org_id, assigned_by=caller.user_id)
    except RoleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return {"assigned": True}


@router.delete("/organizations/{org_id}/rbac/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role_from_user_endpoint(
    org_id: uuid.UUID, user_id: uuid.UUID, role_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    await remove_role_from_user(db, user_id=user_id, role_id=role_id)
    await db.commit()


@router.get("/organizations/{org_id}/rbac/users/{user_id}/permissions", response_model=EffectivePermissionsResponse)
async def get_user_permissions_endpoint(
    org_id: uuid.UUID, user_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    target_membership = await get_organization_member_or_404(db, org_id, user_id)
    from api.models.organization import OrganizationRole

    is_admin_or_owner = target_membership.role in (OrganizationRole.owner, OrganizationRole.admin)
    permissions = await get_user_effective_permissions(db, user_id=user_id, organization_id=org_id)
    return EffectivePermissionsResponse(user_id=user_id, organization_id=org_id, permissions=sorted(permissions), is_org_admin_or_owner=is_admin_or_owner)


@router.post("/rbac/check", response_model=PermissionCheckResponse)
async def check_permission_endpoint(payload: PermissionCheckRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Member+ -- any org member can ask "can I do X", scoped to
    themselves only (never another user_id, unlike the Admin+ endpoints
    above); membership itself is verified the same anti-enumeration way
    as every other org-scoped lookup (404, not 403, for a non-member)."""
    from sqlalchemy import select

    membership = await db.scalar(
        select(OrganizationMember).where(OrganizationMember.organization_id == payload.organization_id, OrganizationMember.user_id == current_user.id)
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    from api.models.organization import OrganizationRole

    if membership.role in (OrganizationRole.owner, OrganizationRole.admin):
        return PermissionCheckResponse(allowed=True)
    allowed = await check_permission(db, user_id=current_user.id, organization_id=payload.organization_id, resource=payload.resource, action=payload.action)
    return PermissionCheckResponse(allowed=allowed)
