"""
Partie 10.1 -- FastAPI dependency factories that gate a route on a
granular `resource:action` permission, real and live-wired (unlike the
pre-existing, deliberately-unwired Casbin scaffold at
api/security/rbac.py -- see that module's own docstring for why it was
left inert). Named to match this étape's own literal spec
(require_permission/require_role/require_any_permission/
require_all_permissions) even though they're implemented as FastAPI
`Depends(...)` factories rather than Python decorators: a real decorator
wrapping a route handler has no way to receive FastAPI's own dependency
injection (the request, the DB session, `org_id` from the path) without
re-implementing it, which is exactly the wrong direction for a codebase
that already has a working, tested Depends-based authorization layer
(api/security/organizations.py's require_org_admin, etc.) this is meant
to extend, not replace.

Every check here treats Owner/Admin (api/models/organization.py's
OrganizationRole) as implicitly holding every permission -- the fixed
hierarchy already means they can do anything a router permits; a
CustomRole is for granting a NARROWER slice of that to a Member or
Viewer who doesn't already have it, not a second gate on top of Owner/
Admin's existing authority.
"""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_current_user
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.organizations import require_org_member
from api.services.rbac_custom import get_user_effective_permissions

_FORBIDDEN = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


async def _effective_permissions_for(db: AsyncSession, membership: OrganizationMember) -> set[str] | None:
    """None is a sentinel meaning "every permission" (Owner/Admin) rather
    than an actual set, so callers never need to enumerate all 52 keys
    just to express "this membership already has full access."""
    if membership.role in (OrganizationRole.owner, OrganizationRole.admin):
        return None
    return await get_user_effective_permissions(db, user_id=membership.user_id, organization_id=membership.organization_id)


def require_permission(permission_key: str):
    """`Depends(require_permission("documents:read"))` on any route
    shaped `/organizations/{org_id}/...` -- Owner/Admin always pass;
    everyone else needs a CustomRole granting exactly this key (or the
    `resource:manage` key, already expanded into read/write/delete by
    get_user_effective_permissions)."""

    async def _dependency(membership: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)) -> OrganizationMember:
        effective = await _effective_permissions_for(db, membership)
        if effective is not None and permission_key not in effective:
            raise _FORBIDDEN
        return membership

    return _dependency


def require_any_permission(permission_keys: list[str]):
    async def _dependency(membership: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)) -> OrganizationMember:
        effective = await _effective_permissions_for(db, membership)
        if effective is not None and not (effective & set(permission_keys)):
            raise _FORBIDDEN
        return membership

    return _dependency


def require_all_permissions(permission_keys: list[str]):
    async def _dependency(membership: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)) -> OrganizationMember:
        effective = await _effective_permissions_for(db, membership)
        if effective is not None and not set(permission_keys).issubset(effective):
            raise _FORBIDDEN
        return membership

    return _dependency


def require_role(role_name: str):
    """Checks the caller's FIXED OrganizationRole (owner/admin/manager/
    member/viewer) -- distinct from require_permission, which checks a
    CustomRole's granted permissions. `role_name` must be one of
    OrganizationRole's own values."""
    try:
        target = OrganizationRole(role_name)
    except ValueError as exc:
        raise ValueError(f"Unknown role {role_name!r} -- must be one of {[r.value for r in OrganizationRole]}") from exc

    _RANK = {OrganizationRole.viewer: 0, OrganizationRole.member: 1, OrganizationRole.manager: 2, OrganizationRole.admin: 3, OrganizationRole.owner: 4}

    async def _dependency(membership: OrganizationMember = Depends(require_org_member)) -> OrganizationMember:
        if _RANK[membership.role] < _RANK[target]:
            raise _FORBIDDEN
        return membership

    return _dependency
