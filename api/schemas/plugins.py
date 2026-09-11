"""Partie 16 (ter) -- plugin marketplace request/response bodies."""

import datetime as dt
import uuid

from pydantic import BaseModel

from api.models.plugins import PluginCategory, PluginExecutionStatus, PluginStatus


class PermissionResponse(BaseModel):
    id: str
    label: str


class PluginResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    description: str
    category: PluginCategory
    manifest: dict
    version: str
    code_size_bytes: int
    status: PluginStatus
    rejection_reason: str | None
    install_count: int
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


class PluginVersionResponse(BaseModel):
    id: uuid.UUID
    plugin_id: uuid.UUID
    version: str
    manifest: dict
    code_size_bytes: int
    changelog: str | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class PluginExecutionRequest(BaseModel):
    data: dict = {}


class PluginExecutionResponse(BaseModel):
    id: uuid.UUID
    plugin_id: uuid.UUID
    organization_id: uuid.UUID
    installation_id: uuid.UUID | None
    hook: str | None
    status: PluginExecutionStatus
    input_payload: dict
    output_payload: dict | None
    error_message: str | None
    duration_ms: int | None
    created_at: dt.datetime

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
