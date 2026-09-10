"""Request/response bodies for Partie 13 (metrics summary + alerting/incidents)."""

import datetime as dt
import uuid

from pydantic import BaseModel

from api.models.alerting import AlertChannelType, AlertOperator, AlertSeverity, IncidentStatus


class MetricsSummaryResponse(BaseModel):
    business: dict
    http_requests_total_samples: int
    celery_tasks_total_samples: int
    request_duration_observation_count: int


class AlertChannelResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: AlertChannelType
    config: dict
    enabled: bool

    model_config = {"from_attributes": True}


class AlertChannelCreateRequest(BaseModel):
    name: str
    type: AlertChannelType
    config: dict


class AlertChannelUpdateRequest(BaseModel):
    name: str | None = None
    config: dict | None = None
    enabled: bool | None = None


class AlertRuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    metric: str
    operator: AlertOperator
    threshold: float
    severity: AlertSeverity
    channel_id: uuid.UUID | None
    enabled: bool

    model_config = {"from_attributes": True}


class AlertRuleCreateRequest(BaseModel):
    name: str
    metric: str
    operator: AlertOperator
    threshold: float
    severity: AlertSeverity = AlertSeverity.medium
    channel_id: uuid.UUID | None = None


class AlertRuleUpdateRequest(BaseModel):
    name: str | None = None
    metric: str | None = None
    operator: AlertOperator | None = None
    threshold: float | None = None
    severity: AlertSeverity | None = None
    channel_id: uuid.UUID | None = None
    enabled: bool | None = None


class AlertRuleTestResponse(BaseModel):
    metric: str
    current_value: float | None
    would_trigger: bool


class AlertHistoryResponse(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    triggered_at: dt.datetime
    value_at_trigger: float
    message: str
    notified: bool

    model_config = {"from_attributes": True}


class IncidentResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    severity: AlertSeverity
    status: IncidentStatus
    created_at: dt.datetime
    resolved_at: dt.datetime | None

    model_config = {"from_attributes": True}


class IncidentCreateRequest(BaseModel):
    title: str
    description: str | None = None
    severity: AlertSeverity = AlertSeverity.medium


class IncidentUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: AlertSeverity | None = None
    status: IncidentStatus | None = None
