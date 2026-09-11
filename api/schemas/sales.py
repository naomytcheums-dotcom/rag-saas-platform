"""Request/response bodies for Partie 16 (bis): self-hosted license, hybrid support/SLA, white-label reseller."""

import datetime as dt
import uuid

from pydantic import BaseModel

from api.models.sales import LicenseStatus, TicketPriority, TicketStatus


class GenerateLicenseRequest(BaseModel):
    plan_key: str
    max_activations: int = 1
    expires_in_days: int | None = 365


class LicenseResponse(BaseModel):
    id: uuid.UUID
    key: str
    plan_key: str
    status: LicenseStatus
    max_activations: int
    activation_count: int
    expires_at: dt.datetime | None
    activated_at: dt.datetime | None

    model_config = {"from_attributes": True}


class ValidateLicenseRequest(BaseModel):
    key: str


class ActivateLicenseRequest(BaseModel):
    key: str


class CreateTicketRequest(BaseModel):
    subject: str
    description: str
    priority: TicketPriority = TicketPriority.normal


class TicketResponseModel(BaseModel):
    id: uuid.UUID
    subject: str
    description: str
    priority: TicketPriority
    status: TicketStatus
    created_at: dt.datetime
    first_responded_at: dt.datetime | None
    resolved_at: dt.datetime | None

    model_config = {"from_attributes": True}


class RespondTicketRequest(BaseModel):
    body: str


class TicketMessageResponse(BaseModel):
    id: uuid.UUID
    body: str
    is_staff: bool
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class CreateResellerRequest(BaseModel):
    organization_id: uuid.UUID
    commission_percent: int = 20


class ResellerResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    commission_percent: int
    is_active: bool

    model_config = {"from_attributes": True}


class AddSubClientRequest(BaseModel):
    organization_id: uuid.UUID


class SubClientResponse(BaseModel):
    id: uuid.UUID
    reseller_id: uuid.UUID
    organization_id: uuid.UUID
    created_at: dt.datetime

    model_config = {"from_attributes": True}
