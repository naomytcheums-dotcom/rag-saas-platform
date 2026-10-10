"""Spec 15.1 -- human escalation tickets (API schemas)."""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["low", "medium", "high", "critical"]
Status = Literal["open", "assigned", "resolved", "closed"]


class EscalationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_run_id: uuid.UUID
    organization_id: uuid.UUID | None
    issue: str
    context: dict | None
    priority: str
    status: str
    resolution: str | None
    assignee_id: uuid.UUID | None
    created_at: dt.datetime
    resolved_at: dt.datetime | None
    sla_due_at: dt.datetime | None
    sla_breached: bool = False


class EscalationListResponse(BaseModel):
    items: list[EscalationResponse]
    total: int
    limit: int
    offset: int


class EscalationUpdateRequest(BaseModel):
    priority: Priority | None = None
    status: Status | None = None
    resolution: str | None = Field(default=None, max_length=10000)


class EscalationAssignRequest(BaseModel):
    assignee_id: uuid.UUID


class EscalationNoteCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class EscalationNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    escalation_id: uuid.UUID
    author_id: uuid.UUID | None
    body: str
    created_at: dt.datetime


class EscalationStatsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    sla_breached: int
