"""Request/response bodies for Partie 20 -- advanced analytics
(api/routers/analytics.py)."""

import datetime as dt
import uuid

from pydantic import BaseModel


class TrackEventRequest(BaseModel):
    event_type: str
    event_data: dict = {}


class MetricPointResponse(BaseModel):
    metric_name: str
    metric_value: float
    period: str
    period_start: dt.datetime


class EventResponse(BaseModel):
    id: str
    event_type: str
    event_data: dict
    user_id: str | None
    created_at: str


class CreateDashboardRequest(BaseModel):
    name: str
    widgets: list = []
    is_default: bool = False


class UpdateDashboardRequest(BaseModel):
    name: str | None = None
    widgets: list | None = None
    is_default: bool | None = None


class DashboardResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    widgets: list
    is_default: bool
    created_at: dt.datetime

    model_config = {"from_attributes": True}
