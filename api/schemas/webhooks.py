"""Request/response bodies for Partie 9.2.7."""

import datetime as dt
import uuid

from pydantic import BaseModel, field_validator

from api.services.outbound_http import validate_outbound_url


class WebhookCreateRequest(BaseModel):
    name: str
    url: str
    events: list[str]
    headers: dict | None = None
    secret: str | None = None

    @field_validator("url")
    @classmethod
    def _url_is_a_public_http_url(cls, value: str) -> str:
        return validate_outbound_url(value)


class WebhookUpdateRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    events: list[str] | None = None
    headers: dict | None = None
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def _url_is_a_public_http_url(cls, value: str | None) -> str | None:
        return validate_outbound_url(value) if value is not None else value


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
