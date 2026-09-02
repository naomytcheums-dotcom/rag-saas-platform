"""Request/response bodies for api/routers/usage.py (Partie 1.3.8)."""

import datetime as dt
import uuid

from pydantic import BaseModel


class UsageDayEntry(BaseModel):
    date: dt.date
    metrics: dict[str, int]


class UsageResponse(BaseModel):
    """GET /organizations/{org_id}/usage. Shape depends on whether the
    `metric` query parameter was supplied:

    - `metric` given: `metric`/`total` are populated, `total_by_metric`/
      `by_day` are None -- a single-metric aggregate (get_usage).
    - `metric` omitted: `total_by_metric`/`by_day` are populated,
      `metric`/`total` are None -- the full résumé (get_usage_summary).
    """

    organization_id: uuid.UUID
    start_date: dt.date | None
    end_date: dt.date | None
    metric: str | None = None
    total: int | None = None
    total_by_metric: dict[str, int] | None = None
    by_day: list[UsageDayEntry] | None = None


class UsageDetailEntry(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    timestamp: dt.datetime
    metric: str
    value: int
    metadata: dict | None


class UsageDetailListResponse(BaseModel):
    items: list[UsageDetailEntry]
    total: int
    limit: int
    offset: int
