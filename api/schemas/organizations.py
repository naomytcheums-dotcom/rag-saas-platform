"""Request/response bodies for api/routers/organizations.py (Etape 1.2.2)
and api/routers/organization_members.py (Etape 1.2.3)."""

import datetime as dt
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from api.models.organization import OrganizationRole


class OrganizationCreateRequest(BaseModel):
    """Body of POST /organizations."""

    name: str = Field(min_length=1, max_length=200)


class OrganizationUpdateRequest(BaseModel):
    """Body of PATCH /organizations/{id} -- Owner only."""

    name: str = Field(min_length=1, max_length=200)


class OrganizationEntry(BaseModel):
    """One organization, from the calling user's own point of view --
    `my_role` is THIS user's role in it, never another member's."""

    id: uuid.UUID
    name: str
    slug: str
    my_role: OrganizationRole
    created_at: dt.datetime
    updated_at: dt.datetime


class OrganizationListResponse(BaseModel):
    items: list[OrganizationEntry]


def _reject_owner_role(value: OrganizationRole) -> OrganizationRole:
    """Shared by both request schemas below -- Owner can't be granted
    through the generic member-management endpoints, only through a
    (not-yet-built) dedicated ownership-transfer flow. See
    api/security/organizations.py's reject_if_target_is_owner for the
    matching check on the EXISTING-member side."""
    if value == OrganizationRole.owner:
        raise ValueError("Cannot assign the Owner role here -- ownership transfer is not yet implemented")
    return value


class OrganizationMemberInviteRequest(BaseModel):
    """Body of POST /organizations/{org_id}/members/invite. Adds an
    EXISTING account to the organization immediately -- this app has no
    email-based invitation link yet (item 1.3.4), so an email with no
    matching account gets a 404, not an invitation to sign up."""

    email: EmailStr
    role: OrganizationRole = OrganizationRole.member

    @field_validator("role")
    @classmethod
    def _role_not_owner(cls, value: OrganizationRole) -> OrganizationRole:
        return _reject_owner_role(value)


class OrganizationMemberRoleUpdateRequest(BaseModel):
    """Body of PATCH /organizations/{org_id}/members/{user_id}/role."""

    role: OrganizationRole

    @field_validator("role")
    @classmethod
    def _role_not_owner(cls, value: OrganizationRole) -> OrganizationRole:
        return _reject_owner_role(value)


class OrganizationMemberEntry(BaseModel):
    user_id: uuid.UUID
    email: str
    role: OrganizationRole
    invited_by: uuid.UUID | None
    joined_at: dt.datetime


class OrganizationMemberListResponse(BaseModel):
    items: list[OrganizationMemberEntry]
