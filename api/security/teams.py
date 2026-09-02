"""
Partie 1.3.3 -- Teams. Two independent axes combine here: a team's OWN
admin/member role (api/models/team.py's TeamRole), and the caller's
organization role (Etape 1.2.2-1.2.6). Neither replaces the other:

- An org Owner/Admin/Manager can always view or manage ANY team in
  their organization, even one they were never personally added to --
  an administrative override, the same "higher org tiers can always
  reach into org-scoped resources" pattern require_org_admin/owner
  already establish. Without this, a team whose only team-admin has
  left the company would become unmanageable by anyone.
- A team's own "admin" role only grants membership-management power
  WITHIN that one team -- it never surpasses org-level roles, and never
  grants anything outside that team. Teams cannot escalate a Member into
  organization-wide power by being made a team admin.

So require_team_member/require_team_admin are each an OR of "the
team-specific role" and "the org-level override" -- never a narrowing of
what org roles already allow, purely an ADDITIONAL way in for someone
who's on the team without necessarily being an org Manager+.

Every check here ALSO re-verifies the caller is still a member of the
team's organization at all (not just that a TeamMember row exists) --
defense in depth against a stale team_members row surviving a since-
revoked organization membership; api/routers/organization_members.py's
remove_organization_member additionally cleans these rows up directly,
but a permission check should never rely SOLELY on cleanup elsewhere
having run correctly.
"""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_current_user
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.team import Team, TeamMember, TeamRole
from api.models.user import User

_ORG_MANAGER_TIERS = (OrganizationRole.owner, OrganizationRole.admin, OrganizationRole.manager)


async def _resolve_team_and_org_membership(
    team_id: uuid.UUID, current_user: User, db: AsyncSession,
) -> tuple[Team, OrganizationMember | None, TeamMember | None]:
    """Returns (team, caller's org membership or None, caller's team
    membership or None). A non-member of the team's organization gets
    None for both -- callers raise 404 in that case, same anti-
    enumeration reasoning as require_org_member: a team's existence
    (and which organization it belongs to) isn't information a
    non-member of that organization should learn from a permission
    error alone."""
    team = await db.get(Team, team_id)
    if team is None:
        return None, None, None

    org_membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == team.organization_id, OrganizationMember.user_id == current_user.id,
        )
    )
    if org_membership is None:
        return team, None, None

    team_membership = await db.scalar(
        select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == current_user.id)
    )
    return team, org_membership, team_membership


async def check_user_in_team(db: AsyncSession, *, user_id: uuid.UUID, team_id: uuid.UUID) -> bool:
    """Item 5's literal function -- a plain existence check, no org-role
    override (unlike require_team_member below): used where the caller
    wants to know about ACTUAL team membership specifically, not "can
    this caller reach this team's data by any means"."""
    return (
        await db.scalar(select(TeamMember.id).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id))
    ) is not None


async def require_team_member(
    team_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[Team, TeamMember | None]:
    """Returns (team, caller's team membership -- None if they're only
    here via the org-Manager+ override, never via a team_members row).
    404 for "no such team", "not a member of its organization at all",
    and "org member but neither on the team nor Manager+" -- all
    collapsed into one response, same anti-enumeration shape as
    require_org_member."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    team, org_membership, team_membership = await _resolve_team_and_org_membership(team_id, current_user, db)
    if team is None or org_membership is None:
        raise not_found

    if team_membership is None and org_membership.role not in _ORG_MANAGER_TIERS:
        raise not_found

    return team, team_membership


async def require_team_admin(
    team_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[Team, TeamMember | None]:
    """Same shape as require_team_member, but requires either
    TeamRole.admin on the team specifically, or the org Manager+
    override -- being merely a `member` of the team is not enough to
    manage who else is on it."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    team, org_membership, team_membership = await _resolve_team_and_org_membership(team_id, current_user, db)
    if team is None or org_membership is None:
        raise not_found

    is_org_override = org_membership.role in _ORG_MANAGER_TIERS
    is_team_admin = team_membership is not None and team_membership.role == TeamRole.admin
    if not is_org_override and not is_team_admin:
        if team_membership is None:
            # Not on the team at all, and no org override -- same
            # anti-enumeration treatment as require_team_member.
            raise not_found
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Team admin access required")

    return team, team_membership


async def require_team_org_manager(
    team_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> Team:
    """
    Gates renaming/deleting a team itself (PATCH/DELETE /teams/{id}) --
    deliberately Owner/Admin/Manager of the ORGANIZATION, not
    require_team_admin. A team's own admin manages who's ON the team;
    whether the team exists at all is an organization-level
    administrative concern, the same boundary
    api/security/workspaces.py draws between workspace membership and
    workspace CRUD.
    """
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    team = await db.get(Team, team_id)
    if team is None:
        raise not_found

    org_membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == team.organization_id, OrganizationMember.user_id == current_user.id,
        )
    )
    if org_membership is None:
        raise not_found

    if org_membership.role not in _ORG_MANAGER_TIERS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization manager access required")

    return team
