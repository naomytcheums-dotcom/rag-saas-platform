"""
Partie 1.3.3 -- Teams. Creating a team requires org Manager+
(require_org_manager, api/security/organizations.py) -- the creator is
added as that team's own admin in the same transaction, mirroring
api/security/organizations.py's create_organization_with_owner (an
organization and its founding Owner membership are never created
without each other; same here for a team and its founding admin).

Renaming/deleting a team stays org Manager+ (require_team_org_manager);
managing WHO is on the team is require_team_admin (the team's own admin
role, OR the same org Manager+ override) -- see
api/security/teams.py's module docstring for the full reasoning.

No "last team admin" protection, unlike the org-level "last superadmin"
rule (api/routers/admin_users.py) or the Owner-untouchable rule
(api/security/organizations.py's reject_if_target_is_owner): a team
with zero admins is not a lockout, since org Manager+ can always still
reach and fix it (the escape hatch require_team_admin already builds
in) -- there is no equivalent escape hatch at the organization or
superadmin level, which is why those two rules exist and this one
doesn't.

Partie 1.3.7: create_team now uses require_team_creation_allowed()
(api/security/user_limits.py) instead of require_org_manager directly
-- same restrictive-layer reasoning as api/routers/workspaces.py's
create_workspace. list_teams stays on require_org_manager, unaffected:
this step names no per-member "can list teams" override.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.audit_log import AuditAction
from api.models.organization import OrganizationMember
from api.models.team import Team, TeamMember, TeamRole
from api.models.user import User
from api.schemas.teams import (
    TeamCreateRequest,
    TeamEntry,
    TeamListResponse,
    TeamMemberAddRequest,
    TeamMemberEntry,
    TeamMemberListResponse,
    TeamMemberRoleUpdateRequest,
    TeamUpdateRequest,
)
from api.security.audit_log import log_audit_action
from api.security.organizations import require_org_manager
from api.security.quotas import require_quota_available
from api.security.teams import require_team_admin, require_team_member, require_team_org_manager
from api.security.usage import record_usage
from api.security.user_limits import require_team_creation_allowed
from api.utils import client_ip

router = APIRouter(tags=["teams"])
logger = logging.getLogger(__name__)


def _to_entry(team: Team) -> TeamEntry:
    return TeamEntry(
        id=team.id, organization_id=team.organization_id, name=team.name, description=team.description,
        created_by=team.created_by, created_at=team.created_at, updated_at=team.updated_at,
    )


@router.get("/organizations/{org_id}/teams", response_model=TeamListResponse)
async def list_teams(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Team).where(Team.organization_id == org_id).order_by(Team.created_at.asc())
    )).scalars().all()
    return TeamListResponse(items=[_to_entry(t) for t in rows])


@router.post("/organizations/{org_id}/teams", response_model=TeamEntry, status_code=status.HTTP_201_CREATED)
async def create_team(
    org_id: uuid.UUID, payload: TeamCreateRequest, request: Request,
    caller: OrganizationMember = Depends(require_team_creation_allowed()), db: AsyncSession = Depends(get_db),
):
    await require_quota_available(db, org_id, "teams")  # Partie 1.3.6 -- checked against max_teams

    team = Team(organization_id=org_id, name=payload.name, description=payload.description, created_by=caller.user_id)
    db.add(team)
    await db.flush()

    db.add(TeamMember(team_id=team.id, user_id=caller.user_id, role=TeamRole.admin))

    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.TEAM_CREATED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={"organization_id": str(org_id), "team_id": str(team.id), "name": payload.name},
    )
    # Partie 1.3.8 -- see api/routers/workspaces.py's create_workspace for
    # the same reasoning.
    await record_usage(db, org_id, "teams_created", 1, user_id=caller.user_id, metadata={"team_id": str(team.id)})
    await db.commit()
    await db.refresh(team)
    return _to_entry(team)


@router.get("/teams/{team_id}", response_model=TeamEntry)
async def get_team(caller_ctx: tuple[Team, TeamMember | None] = Depends(require_team_member)):
    team, _membership = caller_ctx
    return _to_entry(team)


@router.patch("/teams/{team_id}", response_model=TeamEntry)
async def update_team(
    payload: TeamUpdateRequest, team: Team = Depends(require_team_org_manager), db: AsyncSession = Depends(get_db),
):
    team.name = payload.name
    team.description = payload.description
    await db.commit()
    # updated_at has onupdate=func.now() -- see api/routers/organizations.py's
    # update_organization for why an explicit refresh is required here.
    await db.refresh(team)
    return _to_entry(team)


@router.delete("/teams/{team_id}")
async def delete_team(
    request: Request, team: Team = Depends(require_team_org_manager),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.TEAM_DELETED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={"organization_id": str(team.organization_id), "team_id": str(team.id), "name": team.name},
    )
    await db.execute(delete(Team).where(Team.id == team.id))
    await db.commit()
    return {"message": "Team deleted"}


@router.get("/teams/{team_id}/members", response_model=TeamMemberListResponse)
async def list_team_members(
    caller_ctx: tuple[Team, TeamMember | None] = Depends(require_team_member), db: AsyncSession = Depends(get_db),
):
    team, _membership = caller_ctx
    rows = (await db.execute(
        select(TeamMember, User.email)
        .join(User, User.id == TeamMember.user_id)
        .where(TeamMember.team_id == team.id)
        .order_by(TeamMember.joined_at.asc())
    )).all()
    return TeamMemberListResponse(items=[
        TeamMemberEntry(user_id=m.user_id, email=email, role=m.role, joined_at=m.joined_at) for m, email in rows
    ])


@router.post("/teams/{team_id}/members", response_model=TeamMemberEntry, status_code=status.HTTP_201_CREATED)
async def add_team_member(
    payload: TeamMemberAddRequest, request: Request,
    caller_ctx: tuple[Team, TeamMember | None] = Depends(require_team_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Adds an EXISTING member of the team's organization -- same
    reasoning as api/schemas/organizations.py's
    OrganizationMemberInviteRequest (no invitation-token flow exists
    yet, item 1.3.4)."""
    team, _caller_membership = caller_ctx

    target_user = await db.scalar(select(User).where(User.email == payload.email))
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No account exists with that email -- they must register first",
        )

    target_org_membership = await db.scalar(
        select(OrganizationMember.id).where(
            OrganizationMember.organization_id == team.organization_id, OrganizationMember.user_id == target_user.id,
        )
    )
    if target_org_membership is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Target user is not a member of this organization",
        )

    already_on_team = await db.scalar(
        select(TeamMember.id).where(TeamMember.team_id == team.id, TeamMember.user_id == target_user.id)
    )
    if already_on_team is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This user is already on the team")

    membership = TeamMember(team_id=team.id, user_id=target_user.id, role=payload.role)
    db.add(membership)
    await db.flush()

    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.TEAM_MEMBER_ADDED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={
            "organization_id": str(team.organization_id), "team_id": str(team.id),
            "target_user_id": str(target_user.id), "role": payload.role.value,
        },
    )
    await db.commit()
    return TeamMemberEntry(user_id=target_user.id, email=target_user.email, role=membership.role, joined_at=membership.joined_at)


@router.patch("/teams/{team_id}/members/{user_id}", response_model=TeamMemberEntry)
async def update_team_member_role(
    user_id: uuid.UUID, payload: TeamMemberRoleUpdateRequest, request: Request,
    caller_ctx: tuple[Team, TeamMember | None] = Depends(require_team_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    team, _caller_membership = caller_ctx

    target_membership = await db.scalar(
        select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.user_id == user_id)
    )
    if target_membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    previous_role = target_membership.role
    target_membership.role = payload.role
    target_email = await db.scalar(select(User.email).where(User.id == user_id))

    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.TEAM_MEMBER_ROLE_CHANGED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={
            "organization_id": str(team.organization_id), "team_id": str(team.id), "target_user_id": str(user_id),
            "previous_role": previous_role.value, "new_role": payload.role.value,
        },
    )
    await db.commit()
    await db.refresh(target_membership)
    return TeamMemberEntry(user_id=user_id, email=target_email, role=target_membership.role, joined_at=target_membership.joined_at)


@router.delete("/teams/{team_id}/members/{user_id}")
async def remove_team_member(
    user_id: uuid.UUID, request: Request,
    caller_ctx: tuple[Team, TeamMember | None] = Depends(require_team_admin),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    team, _caller_membership = caller_ctx

    target_membership = await db.scalar(
        select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.user_id == user_id)
    )
    if target_membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.TEAM_MEMBER_REMOVED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={"organization_id": str(team.organization_id), "team_id": str(team.id), "target_user_id": str(user_id)},
    )
    await db.execute(delete(TeamMember).where(TeamMember.id == target_membership.id))
    await db.commit()
    return {"message": "Member removed"}
