"""Request/response bodies for api/routers/reindex_schedules.py (Partie 2.2.15)."""

import datetime as dt
import uuid

from pydantic import BaseModel


class ReindexScheduleCreateRequest(BaseModel):
    schedule_name: str
    cron_pattern: str
    enabled: bool = True


class ReindexScheduleUpdateRequest(BaseModel):
    schedule_name: str | None = None
    cron_pattern: str | None = None
    enabled: bool | None = None


class ReindexScheduleResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    schedule_name: str
    cron_pattern: str
    enabled: bool
    last_run_at: dt.datetime | None
    next_run_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
