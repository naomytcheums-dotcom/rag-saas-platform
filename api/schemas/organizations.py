"""Request/response bodies for api/routers/organizations.py (Etape 1.2.2)."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field

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
