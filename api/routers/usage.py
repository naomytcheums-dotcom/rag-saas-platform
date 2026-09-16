"""
Partie 1.3.8 -- viewing an organization's usage. All three endpoints are
Admin+ (require_org_admin, Owner or Admin), same tier as
api/routers/quotas.py's GET: usage is the same kind of "how close are we
to a limit" visibility, not a member-management concern.
"""

import csv
import datetime as dt
import io
import json
import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.models.organization_usage import OrganizationUsageDetail
from api.schemas.usage import UsageDayEntry, UsageDetailEntry, UsageDetailListResponse, UsageResponse
from api.security.organizations import require_org_admin
from api.utils import MAX_PAGE_SIZE
from api.security.usage import get_usage, get_usage_summary

router = APIRouter(tags=["usage"])



@router.get("/organizations/{org_id}/usage", response_model=UsageResponse)
async def get_organization_usage(
    org_id: uuid.UUID, metric: str | None = None,
    start_date: dt.date | None = None, end_date: dt.date | None = None,
    _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    """
    `metric` omitted: the full résumé across every metric this
    organization has ever recorded (get_usage_summary) -- total per
    metric, plus a per-day breakdown. `metric` given: just that one
    dimension's summed total over the range (get_usage) -- see
    UsageResponse's own docstring for why the two modes share one
    response shape instead of two separate endpoints.
    """
    if metric is not None:
        total = await get_usage(db, org_id, metric, start_date, end_date)
        return UsageResponse(organization_id=org_id, start_date=start_date, end_date=end_date, metric=metric, total=total)

    summary = await get_usage_summary(db, org_id, start_date, end_date)
    return UsageResponse(
        organization_id=org_id, start_date=start_date, end_date=end_date,
        total_by_metric=summary["total_by_metric"],
        by_day=[UsageDayEntry(**day) for day in summary["by_day"]],
    )


@router.get("/organizations/{org_id}/usage/details", response_model=UsageDetailListResponse)
async def get_organization_usage_details(
    org_id: uuid.UUID, metric: str | None = None, user_id: uuid.UUID | None = None,
    start_date: dt.date | None = None, end_date: dt.date | None = None,
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0),
    _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    """
    The raw, per-event traceability log (item 2's optional
    `organization_usage_details` table) -- who did what, when. Paginated
    (same limit/offset convention as api/routers/audit.py): unlike the
    daily-aggregate table above, this one has no bound on how large it
    can grow, so an unpaginated "list everything" here would be a
    genuine scalability problem, not a hypothetical one.
    """
    filters = [OrganizationUsageDetail.organization_id == org_id]
    if metric is not None:
        filters.append(OrganizationUsageDetail.metric == metric)
    if user_id is not None:
        filters.append(OrganizationUsageDetail.user_id == user_id)
    if start_date is not None:
        filters.append(OrganizationUsageDetail.timestamp >= dt.datetime.combine(start_date, dt.time.min, dt.timezone.utc))
    if end_date is not None:
        filters.append(OrganizationUsageDetail.timestamp <= dt.datetime.combine(end_date, dt.time.max, dt.timezone.utc))

    total = await db.scalar(select(func.count()).select_from(OrganizationUsageDetail).where(*filters)) or 0
    rows = (await db.scalars(
        select(OrganizationUsageDetail).where(*filters).order_by(OrganizationUsageDetail.timestamp.desc()).limit(limit).offset(offset)
    )).all()

    return UsageDetailListResponse(
        items=[
            UsageDetailEntry(
                id=r.id, user_id=r.user_id, timestamp=r.timestamp, metric=r.metric, value=r.value,
                metadata=r.metadata_json,
            )
            for r in rows
        ],
        total=total, limit=limit, offset=offset,
    )


@router.get("/organizations/{org_id}/usage/export")
async def export_organization_usage(
    org_id: uuid.UUID, format: str = Query(default="json", pattern="^(json|csv)$"),
    start_date: dt.date | None = None, end_date: dt.date | None = None,
    _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    """
    Exports the DAILY AGGREGATE (get_usage_summary), never the raw
    detail log -- the detail table has no upper bound on size (see
    get_organization_usage_details above), so a "download everything"
    export reading it directly would be the one endpoint in this step
    most likely to actually hurt this feature's own performance goal.
    A day/metric/value row per line is also the shape a billing or
    reporting consumer actually wants, not one row per raw event.
    """
    summary = await get_usage_summary(db, org_id, start_date, end_date)
    rows = [
        {"date": day["date"].isoformat(), "metric": metric, "value": value}
        for day in summary["by_day"]
        for metric, value in day["metrics"].items()
    ]

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["date", "metric", "value"])
        writer.writeheader()
        writer.writerows(rows)
        return Response(
            content=buffer.getvalue(), media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=usage-{org_id}.csv"},
        )

    return Response(
        content=json.dumps({"organization_id": str(org_id), "usage": rows}, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=usage-{org_id}.json"},
    )
