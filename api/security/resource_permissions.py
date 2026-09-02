"""
Etape 1.2.8 -- per-resource-instance, per-user permission overrides on
top of the organization role hierarchy (Etape 1.2.2-1.2.6): "this one
Viewer can also `update` this one workspace," without changing their
role or anyone else's access.

**Not built on Casbin, unlike Etape 1.2.7's role-tier engine, and
deliberately so.** Casbin's enforce() there works entirely off an
in-memory policy set loaded ONCE at startup -- correct for role-tier
policies (rarely change, safe to be briefly stale). A granular grant is
the opposite: created and REVOKED by an Admin in real time, and a
production deployment realistically runs multiple worker processes,
each with its own separate in-memory Casbin enforcer -- revoking a grant
in one worker would leave it silently still active in every other
worker until each happens to restart. That is a real correctness bug
for a security control, not a performance nitpick, so this module reads
straight from Postgres on every check instead: a single indexed lookup
(the unique constraint's own composite index), always consistent across
every process, no caching layer to keep in sync or go stale. Same
performance category as every other require_* dependency in this
codebase (require_org_member, get_user_org_role, ...), all of which
already do one query per request.

**Priority order, everywhere in this module**: a matching, non-expired
resource_permissions row --> the caller's organization role --> deny.
The granular layer is checked FIRST and, if present, decides the
outcome immediately (there is no explicit "deny" row type -- every row
is a positive grant -- so "a matching row exists" always means allow).
Absence of a row is not a decision -- it falls through to the existing
role check unchanged. This is purely ADDITIVE: it can only widen what a
role would otherwise allow, never narrow it -- an Owner/Admin/Manager
who already passes the role check is never blocked by the absence of a
granular row.

**Which (resource_type, action) pairs are actually enforced today** --
SUPPORTED_RESOURCE_ACTIONS below. The spec's resource table (document,
conversation, agent, workspace, knowledge_base, organization) names
several resource types that don't exist as real tables yet (Parties
2/3, see Etape 1.2.5's own reasoning) and several actions
(configure/share/export/execute) with no corresponding enforcement point
on ANY existing endpoint -- granting one of those today would be a
dangling, meaningless row nothing ever checks. grant_resource_permission()
rejects them (400) rather than silently accepting dead data; the table
schema itself places no such restriction (resource_type/action are
plain strings, not DB enums -- same "a new value should never need a
migration" reasoning as api/models/audit_log.py's AuditAction), so
widening SUPPORTED_RESOURCE_ACTIONS as real endpoints are built (a
document CRUD API, workspace settings, ...) needs no schema change.

Organization-level grants (read/update/delete/manage_members) are
storable and queryable through the functions and endpoints below, but
NOT wired into api/routers/organizations.py's require_org_owner-gated
PATCH/DELETE -- deliberately: those are this system's highest blast-
radius actions (renaming or deleting an entire organization), and
Etape 1.2.2/1.2.3 already established a stricter-than-asked stance
there (Owner-only, no exceptions, not even for Admin). Punching a
granular-override hole into that in this same step was judged not worth
the risk; workspace update/delete (lower blast radius: one workspace,
not the whole organization) is the one live, load-bearing wiring this
step ships (api/security/workspaces.py's require_workspace_permission).
"""

import datetime as dt
import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_current_user
from api.models.resource_permission import ResourcePermission
from api.models.user import User

# resource_type -> the actions grant_resource_permission() will accept
# for it today -- see this module's top docstring for why the list is
# deliberately smaller than the spec's full resource/action table.
SUPPORTED_RESOURCE_ACTIONS: dict[str, frozenset[str]] = {
    "workspace": frozenset({"read", "update", "delete"}),
    "organization": frozenset({"read", "update", "delete", "manage_members"}),
}


async def grant_resource_permission(
    db: AsyncSession, *, user_id: uuid.UUID, organization_id: uuid.UUID, resource_type: str, resource_id: uuid.UUID,
    action: str, granted_by: uuid.UUID, expires_at: dt.datetime | None = None,
) -> ResourcePermission:
    """
    Does NOT commit -- the caller (api/routers/resource_permissions.py)
    owns the transaction boundary, same convention as
    api/security/organizations.py's create_organization_with_owner.

    Deliberately does NOT re-check "can granted_by actually grant this"
    here -- that requires resource-type-specific context (which
    organization owns this resource, what granted_by's role is there)
    that only the caller has already resolved; see
    api/routers/resource_permissions.py's grant_permission for where
    that check actually happens.
    """
    if resource_type not in SUPPORTED_RESOURCE_ACTIONS or action not in SUPPORTED_RESOURCE_ACTIONS[resource_type]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{action}' on resource type '{resource_type}' is not a grantable permission",
        )
    if user_id == granted_by:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot grant a permission to yourself")

    existing = await db.scalar(
        select(ResourcePermission).where(
            ResourcePermission.organization_id == organization_id, ResourcePermission.resource_type == resource_type,
            ResourcePermission.resource_id == resource_id, ResourcePermission.user_id == user_id,
            ResourcePermission.action == action,
        )
    )
    if existing is not None:
        # Re-granting (e.g. extending an expiring permission) updates the
        # existing row rather than violating the unique constraint.
        existing.granted_by = granted_by
        existing.expires_at = expires_at
        await db.flush()
        return existing

    permission = ResourcePermission(
        organization_id=organization_id, resource_type=resource_type, resource_id=resource_id, user_id=user_id,
        action=action, granted_by=granted_by, expires_at=expires_at,
    )
    db.add(permission)
    await db.flush()
    return permission


async def revoke_resource_permission(
    db: AsyncSession, *, user_id: uuid.UUID, resource_type: str, resource_id: uuid.UUID, action: str,
) -> bool:
    """Returns whether a row actually existed to revoke -- lets the
    caller 404 on "there was nothing to revoke" instead of silently
    reporting success. Does NOT commit, same convention as grant above."""
    result = await db.execute(
        delete(ResourcePermission).where(
            ResourcePermission.resource_type == resource_type, ResourcePermission.resource_id == resource_id,
            ResourcePermission.user_id == user_id, ResourcePermission.action == action,
        )
    )
    return result.rowcount > 0


async def check_resource_permission(
    db: AsyncSession, *, user_id: uuid.UUID, resource_type: str, resource_id: uuid.UUID, action: str,
) -> bool:
    """
    The core query -- one indexed lookup, no cache (see this module's
    top docstring for why). `expires_at IS NULL` (never expires) OR
    `expires_at > now()` (still within its window) -- an expired row is
    left in place, not deleted, for audit-trail purposes, so a stale row
    existing is normal and must not be treated as still-granted.
    """
    permission = await db.scalar(
        select(ResourcePermission).where(
            ResourcePermission.resource_type == resource_type, ResourcePermission.resource_id == resource_id,
            ResourcePermission.user_id == user_id, ResourcePermission.action == action,
            (ResourcePermission.expires_at.is_(None)) | (ResourcePermission.expires_at > func.now()),
        )
    )
    return permission is not None


async def get_user_resource_permissions(
    db: AsyncSession, *, user_id: uuid.UUID, resource_type: str | None = None, resource_id: uuid.UUID | None = None,
) -> list[ResourcePermission]:
    """Etape 1.2.8 item 3 -- `resource_type`/`resource_id` narrow the
    listing; omitting both returns every permission ever granted to this
    user, expired or not (GET /users/me/permissions shows expiry status
    rather than hiding expired rows outright, so a user can see what
    they used to have)."""
    query = select(ResourcePermission).where(ResourcePermission.user_id == user_id)
    if resource_type is not None:
        query = query.where(ResourcePermission.resource_type == resource_type)
    if resource_id is not None:
        query = query.where(ResourcePermission.resource_id == resource_id)
    return list((await db.scalars(query.order_by(ResourcePermission.granted_at.desc()))).all())


async def list_permissions_on_resource(
    db: AsyncSession, *, resource_type: str, resource_id: uuid.UUID,
) -> list[ResourcePermission]:
    """Distinct from get_user_resource_permissions above -- this lists
    every USER granted anything on one resource (used by
    GET /resources/{type}/{id}/permissions, an Admin-only view of who
    has access to THIS resource); get_user_resource_permissions instead
    lists everything ONE user has, across resources (matches this step's
    spec signature exactly, used by GET /users/me/permissions)."""
    query = select(ResourcePermission).where(
        ResourcePermission.resource_type == resource_type, ResourcePermission.resource_id == resource_id,
    )
    return list((await db.scalars(query.order_by(ResourcePermission.granted_at.desc()))).all())


def require_resource_permission(resource_type: str, action: str):
    """
    Generic FastAPI dependency for a resource type with no existing
    require_* of its own (documents/conversations/agents/knowledge_base
    -- Parties 2/3, not built yet): grants access ONLY via a granular
    resource_permissions row, no role fallback -- there is no default
    role-based access to fall back to for a resource type with no real
    table or endpoints yet. Not currently used by any route.

    api/security/workspaces.py's require_workspace_permission is the
    one live wiring this step ships, and is its own function rather
    than built on this one: it needs the 404-before-403 workspace/
    membership resolution require_org_member-family dependencies already
    share, which this generic version -- having no fixed resource table
    to resolve membership from -- cannot provide.
    """

    async def _check(
        resource_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
    ) -> uuid.UUID:
        if not await check_resource_permission(db, user_id=current_user.id, resource_type=resource_type, resource_id=resource_id, action=action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Not authorized for {action} on {resource_type}")
        return resource_id

    return _check
