"""
Etape 1.2.2 -- organization creation and role-checking. Mirrors
api/dependencies.py's require_admin/require_superadmin layering
(get_current_user -> require_org_member -> require_org_admin ->
require_org_owner, each stacked on the one before), but scoped per
organization instead of globally, since org membership/role is
per-(user, organization) here rather than a single column on User.
"""

import logging
import re
import secrets
import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_current_user
from api.models.audit_log import AuditAction
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.audit_log import log_audit_action

logger = logging.getLogger(__name__)

_SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    slug = _SLUG_INVALID_CHARS.sub("-", text.lower()).strip("-")
    return slug or "org"


async def generate_unique_slug(db: AsyncSession, base_text: str) -> str:
    """Slugifies `base_text` and appends a short random suffix on
    collision -- a bounded retry loop, not a single guess, since two
    organizations can very plausibly slugify to the same base (e.g. two
    users both named "Acme")."""
    base_slug = _slugify(base_text)
    candidate = base_slug
    while await db.scalar(select(Organization.id).where(Organization.slug == candidate)):
        candidate = f"{base_slug}-{secrets.token_hex(3)}"
    return candidate


async def create_organization_with_owner(
    db: AsyncSession, *, name: str, owner_user_id: uuid.UUID, ip: str | None = None, user_agent: str | None = None,
) -> Organization:
    """
    Shared by POST /organizations (api/routers/organizations.py) and
    the auto-created default organization at registration
    (api/routers/auth.py's register()) -- one place that creates BOTH
    the Organization row and its founding Owner membership atomically,
    so the two can never exist without each other. `invited_by` is left
    NULL on the owner's own membership -- nobody invited them, they
    created it.

    Does not commit -- the caller decides the transaction boundary (at
    registration, this must be part of the SAME commit as the user row
    itself, so a failure here rolls back the whole registration rather
    than leaving a user with no organization at all).
    """
    slug = await generate_unique_slug(db, name)
    organization = Organization(name=name, slug=slug)
    db.add(organization)
    await db.flush()

    db.add(OrganizationMember(
        organization_id=organization.id, user_id=owner_user_id, role=OrganizationRole.owner, invited_by=None,
    ))
    await log_audit_action(
        db, user_id=owner_user_id, action=AuditAction.ORGANIZATION_CREATED, ip=ip, user_agent=user_agent,
        success=True, metadata={"organization_id": str(organization.id), "name": name, "slug": slug},
    )
    await db.flush()
    return organization


async def get_user_org_role(db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID) -> OrganizationRole | None:
    """None means "not a member of this organization at all" -- distinct
    from any real role value, including the lowest (viewer)."""
    return await db.scalar(
        select(OrganizationMember.role).where(
            OrganizationMember.organization_id == org_id, OrganizationMember.user_id == user_id
        )
    )


async def require_org_member(
    org_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
    """
    Base layer: any role at all. `org_id` is a path parameter -- FastAPI
    resolves it into this dependency automatically by name, the same
    way it resolves a route handler's own path parameters, so this
    dependency is used directly on any route shaped
    `/organizations/{org_id}/...`.

    404 for both "no such organization" and "you're not a member of
    it" -- collapsed into one response so a non-member can't use this
    endpoint to probe which organization IDs exist, the same
    anti-enumeration reasoning DELETE /sessions/{id} already uses for a
    session belonging to someone else.
    """
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id, OrganizationMember.user_id == current_user.id
        )
    )
    if membership is None:
        raise not_found
    return membership


# Etape 1.2.5 -- literal alias, same reasoning as require_org_admin_or_owner
# below: this step's spec asks for this name explicitly. Despite the name,
# it is NOT "Member or above, excluding Viewer" -- it is the exact same
# check as require_org_member (any membership at all). Viewer legitimately
# needs this same access for read-only endpoints (GET /organizations/{id},
# GET .../workspaces) -- see docs/AUTH_BACKEND_SETUP.md's Member section
# for why this codebase has never needed a distinct "member-tier or
# higher, excluding viewer" check, and why one shouldn't be silently
# folded into this alias if it's ever needed.
require_org_member_or_higher = require_org_member


async def require_org_manager(membership: OrganizationMember = Depends(require_org_member)) -> OrganizationMember:
    """
    Etape 1.2.4: Owner, Admin, or Manager -- the tier that can invite
    members (with restrictions, see api/routers/organization_members.py)
    and manage workspaces (api/routers/workspaces.py), but NOT change
    member roles or remove members (that stays require_org_admin,
    unchanged by this step -- Manager sits strictly BETWEEN Member and
    Admin, never widening what Admin-gated endpoints already accept).
    """
    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin, OrganizationRole.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization manager access required")
    return membership


async def require_org_admin(membership: OrganizationMember = Depends(require_org_member)) -> OrganizationMember:
    """Owner or Admin. 403, not 404 -- unlike require_org_member above,
    reaching this dependency at all already proves the caller IS a
    member (require_org_member already ran), so confirming a stricter
    tier exists above them leaks nothing a member doesn't already know
    (they can see their own role, and presumably their organization's
    other members)."""
    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin access required")
    return membership


async def require_org_owner(membership: OrganizationMember = Depends(require_org_member)) -> OrganizationMember:
    """Owner only -- gates PATCH/DELETE /organizations/{id} (renaming or
    deleting the organization itself is the Owner's call alone, not
    something an Admin can do)."""
    if membership.role != OrganizationRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization owner access required")
    return membership


# Etape 1.2.3 -- literally the same check as require_org_admin (Admin has
# always meant "Admin or Owner" in this permission model; there is no
# "Admin excluding Owner" tier anywhere). Kept as its own name only
# because the spec for this step asked for it explicitly -- not a
# separate implementation to maintain in parallel.
require_org_admin_or_owner = require_org_admin


async def get_organization_member_or_404(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> OrganizationMember:
    """Shared by every /organizations/{org_id}/members/{user_id}/...
    endpoint (api/routers/organization_members.py) that acts on a
    SPECIFIC target member, distinct from require_org_member (which
    checks the CALLER's own membership) -- this looks up someone else's."""
    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id, OrganizationMember.user_id == user_id
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return membership


def reject_if_target_is_owner(target_membership: OrganizationMember, *, action: str) -> None:
    """
    Etape 1.2.3, item 5: an Owner's role/membership can't be touched
    through the generic member-management endpoints, by ANYONE --
    stricter than the spec's literal "an Admin can't do this" (which
    would still let the Owner act on themselves): since an organization
    has exactly one Owner (enforced at creation, api/security/organizations.py's
    create_organization_with_owner), demoting or removing them here
    would leave the organization with none at all, and unlike
    api/routers/admin_users.py's "last remaining superadmin" check
    (where OTHER superadmins can exist to fix it), there is no
    "transfer ownership" endpoint yet for anyone to undo this with. A
    deliberately stronger rule than asked for, not a narrower one.
    """
    if target_membership.role == OrganizationRole.owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot {action} the organization's Owner",
        )
