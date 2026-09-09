"""Request/response bodies for Partie 9.2.7."""

import datetime as dt
import uuid

from pydantic import BaseModel


class WebhookCreateRequest(BaseModel):
    name: str
    url: str
    events: list[str]
    headers: dict | None = None
    secret: str | None = None


class WebhookUpdateRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    events: list[str] | None = None
    headers: dict | None = None
    is_active: bool | None = None


class WebhookResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    url: str
    events: list[str]
    is_active: bool
    retry_count: int
    timeout: int
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryResponse(BaseModel):
    id: uuid.UUID
    webhook_id: uuid.UUID
    event: str
    status_code: int | None
    error: str | None
    attempt: int
    delivered_at: dt.datetime | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}
