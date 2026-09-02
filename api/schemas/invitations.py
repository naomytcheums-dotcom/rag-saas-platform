"""Request/response bodies for api/routers/invitations.py (Partie 1.3.4)."""

import datetime as dt
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from api.models.organization import OrganizationRole

# bcrypt silently ignores any byte past position 72 -- same reasoning
# (and same constant) as every password field in api/schemas/auth.py.
_BCRYPT_MAX_BYTES = 72


class InvitationCreateRequest(BaseModel):
    """Body of POST /organizations/{org_id}/invitations."""

    email: EmailStr
    role: OrganizationRole = OrganizationRole.member

    @field_validator("role")
    @classmethod
    def _role_not_owner(cls, value: OrganizationRole) -> OrganizationRole:
        # Same reasoning as api/schemas/organizations.py's
        # OrganizationMemberInviteRequest -- Owner can't be granted
        # through a generic invite, only a (not yet built) dedicated
        # ownership-transfer flow.
        if value == OrganizationRole.owner:
            raise ValueError("Cannot invite someone as Owner -- ownership transfer is not yet implemented")
        return value


class InvitationEntry(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    role: OrganizationRole
    invited_by: uuid.UUID | None
    expires_at: dt.datetime
    accepted_at: dt.datetime | None
    created_at: dt.datetime


class InvitationListResponse(BaseModel):
    items: list[InvitationEntry]


class InvitationAcceptRequest(BaseModel):
    """Body of POST /invitations/accept. `password`/`full_name`/
    `accept_terms` only matter when the invited email has no existing
    account yet -- see api/routers/invitations.py's accept_invitation
    for exactly when each is required."""

    token: str
    password: str | None = Field(default=None, min_length=8)
    full_name: str | None = None
    accept_terms: bool = False

    @field_validator("password")
    @classmethod
    def _password_within_bcrypt_limit(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > _BCRYPT_MAX_BYTES:
            raise ValueError(f"password must be at most {_BCRYPT_MAX_BYTES} bytes")
        return value
