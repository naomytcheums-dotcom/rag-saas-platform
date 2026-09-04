"""Request/response bodies for the Partie 2.2.6 tag routes in
api/routers/documents.py -- a separate schema module from
api/schemas/documents.py, matching that module's own domain-per-file
convention."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class DocumentTagCreateRequest(BaseModel):
    """Item 3's own literal `POST .../tags` request body."""

    name: str = Field(min_length=1, max_length=100)
    color: str | None = Field(default=None, max_length=20)


class DocumentTagUpdateRequest(BaseModel):
    """Item 3's own literal `PATCH /tags/{tag_id}` request body --
    both fields optional, only what's given is changed."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, max_length=20)


class DocumentTagResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    color: str | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
