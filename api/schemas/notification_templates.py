"""Request/response bodies for the real DB-backed notification template
CRUD + preview + test endpoints (P2 #6, session SSRF épinglé).

The model (api/models/notification_template.py) is the real,
admin-editable override layer on top of the code-defined TEMPLATES
dict in api/services/notification_templates.py."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class NotificationTemplateCreate(BaseModel):
    notification_type: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    email_subject: str | None = Field(None, max_length=500)
    is_active: bool = True


class NotificationTemplateUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    body: str | None = Field(None, min_length=1)
    email_subject: str | None = Field(None, max_length=500)
    is_active: bool | None = None


class NotificationTemplateResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    notification_type: str
    title: str
    body: str
    email_subject: str | None
    is_active: bool
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


class NotificationTemplatePreviewRequest(BaseModel):
    notification_type: str = Field(..., min_length=1, max_length=64)
    context: dict = Field(default_factory=dict)


class NotificationTemplatePreviewResponse(BaseModel):
    title: str
    body: str
    email_subject: str


class NotificationTestRequest(BaseModel):
    notification_type: str = Field(..., min_length=1, max_length=64)
    context: dict = Field(default_factory=dict)
