"""Request/response bodies for api/routers/resource_permissions.py (Etape 1.2.8)."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class ResourcePermissionGrantRequest(BaseModel):
    """Body of POST /resources/{resource_type}/{resource_id}/permissions."""

    user_id: uuid.UUID
    action: str = Field(min_length=1, max_length=50)
    expires_at: dt.datetime | None = None


class ResourcePermissionEntry(BaseModel):
    id: uuid.UUID
    resource_type: str
    resource_id: uuid.UUID
    user_id: uuid.UUID
    action: str
    granted_by: uuid.UUID | None
    granted_at: dt.datetime
    expires_at: dt.datetime | None
    is_expired: bool


class ResourcePermissionListResponse(BaseModel):
    items: list[ResourcePermissionEntry]
