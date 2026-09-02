"""
Partie 1.3.7 -- per-member overrides on top of the organization role
hierarchy (Etape 1.2.2-1.2.6). Six columns on OrganizationMember itself
(api/models/organization.py) -- one row per (user, organization), so a
limit is always scoped to a specific membership, never bare "this user"
in isolation (the same user can have different limits in different
organizations, exactly like their role already does).

**Three numeric limits (daily_request_limit, max_documents,
max_conversations) have no real resource to enforce against yet** --
same situation as Etape 1.3.6's seven not-yet-tracked quota dimensions,
for the same reason: no request-metering, document, or conversation
table/endpoint exists (Parties 2/3/8/9). `check_user_limit` returns
`True` (not enforced) and `get_user_usage` reports `None` (not
measured, not "0 used") for these three -- stored as configuration,
ready the moment the resource they gate exists.

**The three booleans are NOT symmetric -- read this before wiring a
fourth one in.** Both directions exist here, layered onto the SAME
role-based gates already established:

- `can_create_workspaces` / `can_create_teams` are RESTRICTIVE AND-gates:
  checked ONLY for a caller who already passes require_org_manager
  (Owner/Admin/Manager). Default `True` preserves today's unchanged
  behavior for anyone who already has the role; flipping it to `False`
  lets an Owner/Admin strip workspace- or team-creation from ONE
  specific over-privileged Manager without demoting them. For a Member
  or Viewer, this column is never even consulted -- require_org_manager
  already blocks them before it would be, same as before this step.
- `can_invite_members` is an ADDITIVE OR-gate: checked ONLY for a
  caller who does NOT already pass require_org_manager. Default `False`
  changes nothing (today, only Manager+ can invite); flipping it to
  `True` for a specific Member or Viewer lets THEM invite too, without
  promoting them to Manager. For Owner/Admin/Manager, this column is
  never consulted -- their role already grants it, unconditionally,
  same as before this step.

Picking the SAME direction (all three restrictive, or all three
additive) would have silently changed already-tested behavior one way
or the other: an all-restrictive `can_invite_members` defaulting
`False` would immediately break every existing Manager-can-invite test
(Etape 1.2.4/1.3.4); an all-additive `can_create_workspaces` defaulting
`True` would immediately let every plain Member create workspaces
(breaking Etape 1.2.4's own tests the other way). The direction chosen
per column is the one consistent with what already ships and is
already tested.
"""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_current_user
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.organizations import require_org_manager, require_org_member

_MANAGER_TIERS = (OrganizationRole.owner, OrganizationRole.admin, OrganizationRole.manager)

# resource_type -> OrganizationMember column name, for the three
# numeric limits. No live-count query builder exists for any of them
# (see this module's top docstring) -- unlike Etape 1.3.6's quotas,
# there is no real table to count against even in principle yet.
_LIMIT_COLUMNS = {
    "requests_per_day": "daily_request_limit",
    "documents": "max_documents",
    "conversations": "max_conversations",
}


async def get_user_limits(db: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
    """
    Item 2's literal function, with `organization_id` added: a bare
    `user_id` is ambiguous the moment a user belongs to more than one
    organization (the normal case since Etape 1.2.2's auto-created
    default org), since every one of these six columns lives on the
    (user, organization) membership row, not on the user globally.
    """
    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return {
        "daily_request_limit": membership.daily_request_limit,
        "max_documents": membership.max_documents,
        "max_conversations": membership.max_conversations,
        "can_create_workspaces": membership.can_create_workspaces,
        "can_create_teams": membership.can_create_teams,
        "can_invite_members": membership.can_invite_members,
    }


async def get_user_usage(db: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
    """Item 2's literal function. `None` for all three numeric
    dimensions -- see this module's top docstring for why that's the
    honest answer today, not a bug."""
    return {resource_type: None for resource_type in _LIMIT_COLUMNS}


async def check_user_limit(
    db: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID, resource_type: str, delta: int = 1,
) -> bool:
    """
    Item 2's literal function. `True` (not blocked) for every one of the
    three dimensions this module tracks, unconditionally -- see this
    module's top docstring: there is no usage to measure yet, so
    nothing can be "over" a limit no activity produces. Kept as a real,
    callable function with a stable signature (matching Etape 1.3.6's
    check_quota) rather than deleted, so wiring a real check in later
    (once documents/conversations/request-metering exist) is a change
    to THIS function's body, not a new one call sites need to learn.
    """
    return True


def require_workspace_creation_allowed():
    """
    Restrictive AND-gate for POST /organizations/{org_id}/workspaces --
    require_org_manager first (unchanged), then can_create_workspaces.
    See this module's top docstring for why this direction, not the
    additive one.
    """

    async def _check(membership: OrganizationMember = Depends(require_org_manager)) -> OrganizationMember:
        if not membership.can_create_workspaces:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace creation has been disabled for your account by an organization administrator",
            )
        return membership

    return _check


def require_team_creation_allowed():
    """Restrictive AND-gate for POST /organizations/{org_id}/teams --
    same shape as require_workspace_creation_allowed above."""

    async def _check(membership: OrganizationMember = Depends(require_org_manager)) -> OrganizationMember:
        if not membership.can_create_teams:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Team creation has been disabled for your account by an organization administrator",
            )
        return membership

    return _check


async def require_can_invite_members(
    org_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
    """
    Additive OR-gate for POST/GET /organizations/{org_id}/members[/invite]
    -- Owner/Admin/Manager pass via role alone, unconditionally (matches
    Etape 1.2.4's unchanged behavior); a Member or Viewer passes ONLY if
    their own can_invite_members is True. 404 for a non-member (same
    anti-enumeration base layer require_org_member already provides),
    403 for a member who fails both checks.
    """
    membership = await require_org_member(org_id, current_user, db)
    if membership.role in _MANAGER_TIERS or membership.can_invite_members:
        return membership
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization manager access required")
