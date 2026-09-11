"""Partie 16 (ter) -- plugin marketplace request/response bodies."""

import datetime as dt
import uuid

from pydantic import BaseModel

from api.models.plugins import PluginStatus


class PermissionResponse(BaseModel):
    id: str
    label: str


class PluginResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    description: str
    manifest: dict
    version: str
    code_size_bytes: int
    status: PluginStatus
    rejection_reason: str | None
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


class PluginRejectRequest(BaseModel):
    reason: str


class InstallationResponse(BaseModel):
    id: uuid.UUID
    plugin_id: uuid.UUID
    organization_id: uuid.UUID
    enabled: bool
    config: dict
    installed_at: dt.datetime

    model_config = {"from_attributes": True}


class InstallationUpdateRequest(BaseModel):
    enabled: bool | None = None
    config: dict | None = None


class ReviewRequest(BaseModel):
    rating: int
    comment: str | None = None


class ReviewResponse(BaseModel):
    id: uuid.UUID
    plugin_id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    rating: int
    comment: str | None
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


class RatingSummaryResponse(BaseModel):
    average_rating: float | None
    review_count: int
