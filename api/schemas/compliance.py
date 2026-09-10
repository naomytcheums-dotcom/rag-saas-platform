"""Request/response bodies for Partie 10.4 (GDPR/CCPA)."""

import datetime as dt
import uuid

from pydantic import BaseModel

from api.models.compliance import DataRequestStatus, DataRequestType


class DataRequestCreate(BaseModel):
    request_type: DataRequestType
    details: str | None = None


class DataRequestUpdate(BaseModel):
    status: DataRequestStatus
    resolution_note: str | None = None


class DataRequestResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    request_type: DataRequestType
    status: DataRequestStatus
    details: str | None
    resolution_note: str | None
    created_at: dt.datetime
    processed_at: dt.datetime | None

    model_config = {"from_attributes": True}


class ConsentRequest(BaseModel):
    consent_type: str
    granted: bool


class ConsentResponse(BaseModel):
    consent_type: str
    granted: bool
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class ComplianceStatusResponse(BaseModel):
    gdpr_export_available: bool
    gdpr_erasure_available: bool
    gdpr_consent_tracking_available: bool
    pending_data_requests: int
    unnotified_breaches: int
    compliant: bool


class DataBreachCreate(BaseModel):
    organization_id: uuid.UUID | None = None
    description: str
    affected_user_count: int = 0


class DataBreachResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    description: str
    affected_user_count: int
    created_at: dt.datetime
    notified_at: dt.datetime | None

    model_config = {"from_attributes": True}
