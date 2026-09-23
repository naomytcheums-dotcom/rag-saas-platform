"""Request/response bodies for Phase 5, Étape 4 (in-app + email
notifications). Separate from api/schemas/notifications.py (Twilio
SMS/WhatsApp) -- different feature that happens to share a name."""

import datetime as dt
import uuid

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    type: str
    title: str
    body: str
    data: dict | None
    priority: str
    channel: str
    read_at: dt.datetime | None
    created_at: dt.datetime
    expires_at: dt.datetime | None

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkAllReadResponse(BaseModel):
    marked_count: int


class NotificationPreferenceResponse(BaseModel):
    notification_type: str
    in_app_enabled: bool
    email_enabled: bool

    model_config = {"from_attributes": True}


class NotificationPreferenceUpdateRequest(BaseModel):
    notification_type: str
    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
