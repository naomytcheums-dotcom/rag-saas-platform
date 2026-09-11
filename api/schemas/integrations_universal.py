"""Request/response bodies for Partie 15 (universal inbound integrations + Airbyte)."""

import datetime as dt
import uuid

from pydantic import BaseModel

from api.models.integrations import IntegrationAction, IntegrationLogStatus, IntegrationProvider


class ProviderResponse(BaseModel):
    id: str
    name: str
    description: str


class ConnectionResponse(BaseModel):
    id: uuid.UUID
    name: str
    provider: IntegrationProvider
    action: IntegrationAction
    is_active: bool
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class ConnectionCreateResponse(ConnectionResponse):
    token: str  # shown once, at creation only


class ConnectionCreateRequest(BaseModel):
    name: str
    provider: IntegrationProvider = IntegrationProvider.webhook
    action: IntegrationAction = IntegrationAction.log_only


class ConnectionUpdateRequest(BaseModel):
    name: str | None = None
    action: IntegrationAction | None = None
    is_active: bool | None = None


class ConnectionTestResponse(BaseModel):
    connection_active: bool
    sample_payload: dict
    mapped_payload: dict
    would_run_action: str


class MappingResponse(BaseModel):
    id: uuid.UUID
    source_field: str
    target_field: str
    transform: str | None

    model_config = {"from_attributes": True}


class MappingCreateRequest(BaseModel):
    source_field: str
    target_field: str
    transform: str | None = None


class MappingUpdateRequest(BaseModel):
    source_field: str | None = None
    target_field: str | None = None
    transform: str | None = None


class LogResponse(BaseModel):
    id: uuid.UUID
    status: IntegrationLogStatus
    payload: dict
    detail: str | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class AirbyteSourceDefinitionResponse(BaseModel):
    sourceDefinitionId: str
    name: str
    dockerRepository: str | None = None


class AirbyteConnectionResponse(BaseModel):
    id: uuid.UUID
    name: str
    airbyte_source_id: str
    airbyte_connection_id: str
    source_type: str
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class AirbyteCreateSourceRequest(BaseModel):
    name: str
    source_definition_id: str
    connection_configuration: dict


class AirbyteCreateConnectionRequest(BaseModel):
    name: str
    airbyte_source_id: str
    airbyte_destination_id: str
    source_type: str
    sync_catalog: dict
