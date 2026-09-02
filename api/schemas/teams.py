"""Request/response bodies for api/routers/teams.py (Partie 1.3.3)."""

import datetime as dt
import uuid

from pydantic import BaseModel, EmailStr, Field

from api.models.team import TeamRole


class TeamCreateRequest(BaseModel):
    """Body of POST /organizations/{org_id}/teams."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class TeamUpdateRequest(BaseModel):
    """Body of PATCH /teams/{team_id}."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class TeamEntry(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


class TeamListResponse(BaseModel):
    items: list[TeamEntry]


class TeamMemberAddRequest(BaseModel):
    """Body of POST /teams/{team_id}/members. Adds an EXISTING member of
    the team's organization -- same "no invitation-token flow yet"
    reasoning as api/schemas/organizations.py's
    OrganizationMemberInviteRequest."""

    email: EmailStr
    role: TeamRole = TeamRole.member


class TeamMemberRoleUpdateRequest(BaseModel):
    """Body of PATCH /teams/{team_id}/members/{user_id}."""

    role: TeamRole


class TeamMemberEntry(BaseModel):
    user_id: uuid.UUID
    email: str
    role: TeamRole
    joined_at: dt.datetime


class TeamMemberListResponse(BaseModel):
    items: list[TeamMemberEntry]
