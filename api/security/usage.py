"""
Partie 1.3.8 -- recording and reading per-organization usage. See
api/models/organization_usage.py's module docstring for the two-table
split and the honest-scope reasoning (metric names are entirely
freeform strings; nothing here validates them against a fixed list,
since the real integration points -- see that same docstring -- are
what makes a metric "real," not a registry of allowed names).

No Celery/async dispatch here, by design, not by oversight: every
existing call site (workspace/team creation, member invite/accept,
quota-exceeded) is an infrequent, org-admin-triggered write, nowhere
near a request volume where one extra indexed INSERT + one indexed
UPDATE-or-INSERT per call is a bottleneck. This module's job is
decoupled from HOW it's called, though -- record_usage's signature
doesn't change the day a genuinely high-QPS caller shows up (e.g. a
real /v1/chat, Partie 9, charged per message): swapping this function's
body for "enqueue a Celery task that does the same two writes" would
require touching zero call sites, only this file. Introducing that
queue today, with nothing that calls it more than a handful of times an
hour, would be solving a load problem this deployment doesn't have yet.
"""

import datetime as dt
import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.organization_usage import OrganizationUsage, OrganizationUsageDetail


async def record_usage(
    db: AsyncSession, organization_id: uuid.UUID, metric: str, value: int, *,
    user_id: uuid.UUID | None = None, metadata: dict | None = None,
) -> None:
    """
    Item 3's literal function. Does two things, both against the SAME
    session/transaction as the caller (does not commit -- the caller's
    own commit covers this write too, same convention as
    create_default_quota/create_or_reissue_invitation):

    1. Upserts today's (organization_id, date, metric) row in
       `organization_usage`, incrementing `value` -- read-then-write,
       not a dialect-specific ON CONFLICT, so this stays portable
       across the SQLite fast suite and real Postgres (see
       api/models/organization_usage.py's own docstring for the
       accepted race this implies, mirroring api/security/quotas.py).
    2. Always appends one row to `organization_usage_details`, even
       though the two are redundant for the three counting metrics --
       the detail row is what makes per-user, per-event traceability
       possible at all (item 2's whole point); the daily row is what
       makes GET .../usage fast without ever summing the detail table.
    """
    today = dt.datetime.now(dt.timezone.utc).date()
    daily = await db.scalar(
        select(OrganizationUsage).where(
            OrganizationUsage.organization_id == organization_id,
            OrganizationUsage.date == today,
            OrganizationUsage.metric == metric,
        )
    )
    if daily is None:
        daily = OrganizationUsage(organization_id=organization_id, date=today, metric=metric, value=0)
        db.add(daily)
    daily.value += value

    db.add(OrganizationUsageDetail(
        organization_id=organization_id, user_id=user_id, metric=metric, value=value, metadata_json=metadata,
    ))
    await db.flush()


async def get_usage(
    db: AsyncSession, organization_id: uuid.UUID, metric: str,
    start_date: dt.date | None = None, end_date: dt.date | None = None,
) -> int:
    """Item 3's literal function -- the summed daily total for ONE
    metric, optionally bounded to a date range (both ends inclusive).
    Reads only the pre-aggregated `organization_usage` table, never the
    detail log."""
    filters = [OrganizationUsage.organization_id == organization_id, OrganizationUsage.metric == metric]
    if start_date is not None:
        filters.append(OrganizationUsage.date >= start_date)
    if end_date is not None:
        filters.append(OrganizationUsage.date <= end_date)

    total = await db.scalar(select(func.coalesce(func.sum(OrganizationUsage.value), 0)).where(*filters))
    return int(total or 0)


async def get_usage_summary(
    db: AsyncSession, organization_id: uuid.UUID,
    start_date: dt.date | None = None, end_date: dt.date | None = None,
) -> dict:
    """
    Item 3's literal function -- a résumé across ALL metrics at once:
    total per metric, and a per-day breakdown. One query against the
    daily-aggregate table (never the potentially huge detail log),
    grouped in Python rather than SQL -- the row count here is at most
    (number of distinct metrics) x (number of days in range), small
    enough that a second GROUP BY query would be pure overhead.
    """
    filters = [OrganizationUsage.organization_id == organization_id]
    if start_date is not None:
        filters.append(OrganizationUsage.date >= start_date)
    if end_date is not None:
        filters.append(OrganizationUsage.date <= end_date)

    rows = (await db.execute(
        select(OrganizationUsage.date, OrganizationUsage.metric, OrganizationUsage.value).where(*filters)
    )).all()

    total_by_metric: dict[str, int] = defaultdict(int)
    by_day: dict[dt.date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row_date, metric, value in rows:
        total_by_metric[metric] += value
        by_day[row_date][metric] += value

    return {
        "total_by_metric": dict(total_by_metric),
        "by_day": [
            {"date": day, "metrics": dict(metrics)}
            for day, metrics in sorted(by_day.items())
        ],
    }
