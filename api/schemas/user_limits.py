"""Request/response bodies for api/routers/user_limits.py (Partie 1.3.7)."""

import uuid

from pydantic import BaseModel, Field


class UserLimitsEntry(BaseModel):
    daily_request_limit: int | None
    max_documents: int | None
    max_conversations: int | None
    can_create_workspaces: bool
    can_create_teams: bool
    can_invite_members: bool


class UserLimitsUsageEntry(BaseModel):
    # All three are always None today -- see api/security/user_limits.py's
    # module docstring for why (no real resource to measure yet).
    requests_per_day: int | None
    documents: int | None
    conversations: int | None


class MemberLimitsResponse(BaseModel):
    organization_id: uuid.UUID
    user_id: uuid.UUID
    limits: UserLimitsEntry
    usage: UserLimitsUsageEntry


class MyLimitsResponse(BaseModel):
    """Body of GET /users/me/limits -- a LIST, not a single object: the
    caller may belong to several organizations (the normal case since
    every account gets a default one at registration), each with its
    own independent limits on this same user's membership row."""

    items: list[MemberLimitsResponse]


class UserLimitsUpdateRequest(BaseModel):
    """Body of PATCH /organizations/{org_id}/members/{user_id}/limits --
    every field optional, only the ones actually sent are changed
    (partial update). Sending a numeric field as JSON `null` explicitly
    clears it back to "no personal limit set" -- distinct from omitting
    the field entirely, which leaves it untouched."""

    daily_request_limit: int | None = Field(default=None, ge=0)
    max_documents: int | None = Field(default=None, ge=0)
    max_conversations: int | None = Field(default=None, ge=0)
    can_create_workspaces: bool | None = None
    can_create_teams: bool | None = None
    can_invite_members: bool | None = None
