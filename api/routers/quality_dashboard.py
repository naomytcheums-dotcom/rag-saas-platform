"""
Partie 6.2.12 -- the real quality dashboard. All 5 endpoints are
Admin+ (`require_org_admin`, Owner or Admin), same tier as
`api/routers/usage.py`'s own: aggregate quality metrics are the same
kind of "how is this organization doing" visibility, not a
member-management concern."""

import csv
import io
import json
import uuid

from fastapi import APIRouter, Depends, Query, Response as FastAPIResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.schemas.quality_dashboard import (
    QualityDashboardResponse, QualityResponseListResponse, QualityTrendsResponse,
)
from api.security.permissions import require_permission
from api.security.organizations import require_org_admin
from api.utils import MAX_PAGE_SIZE
from api.services.quality_dashboard import (
    export_quality_metrics, get_quality_dashboard, get_quality_responses, get_quality_trends,
)

router = APIRouter(tags=["quality-dashboard"])



@router.get("/organizations/{org_id}/quality/dashboard", response_model=QualityDashboardResponse)
async def get_quality_dashboard_endpoint(
    org_id: uuid.UUID, period: int | None = Query(default=None, ge=1),
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    return await get_quality_dashboard(db, org_id, period)


@router.get("/organizations/{org_id}/quality/metrics", response_model=QualityDashboardResponse)
async def get_quality_metrics_endpoint(
    org_id: uuid.UUID, period: int | None = Query(default=None, ge=1),
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    """A real, narrower view than the dashboard above -- just the
    aggregate metrics, same real `QualityDashboardResponse` shape with
    `status_distribution`/`top_*` left unset, for a caller that only
    wants the numbers."""
    dashboard = await get_quality_dashboard(db, org_id, period)
    return {"enabled": dashboard["enabled"], "metrics": dashboard.get("metrics")}


@router.get("/organizations/{org_id}/quality/trends", response_model=QualityTrendsResponse)
async def get_quality_trends_endpoint(
    org_id: uuid.UUID, period: int | None = Query(default=None, ge=1), metric: str = "confidence_score",
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    points = await get_quality_trends(db, org_id, period, metric)
    return QualityTrendsResponse(metric=metric, points=points)


@router.get("/organizations/{org_id}/quality/responses", response_model=QualityResponseListResponse)
async def get_quality_responses_endpoint(
    org_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0),
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    return await get_quality_responses(db, org_id, limit=limit, offset=offset)


@router.get("/organizations/{org_id}/quality/export")
async def export_quality_metrics_endpoint(
    org_id: uuid.UUID, format: str = Query(default="json", pattern="^(json|csv)$"), period: int | None = Query(default=None, ge=1),
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    export = await export_quality_metrics(db, org_id, period)

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["metric", "date", "value"])
        writer.writeheader()
        for name, key in (("avg_confidence_score", "confidence_score"), ("avg_groundedness_score", "groundedness_score"),
                          ("avg_faithfulness_score", "faithfulness_score"), ("avg_hallucination_score", "hallucination_score")):
            writer.writerow({"metric": name, "date": "", "value": export["metrics"].get(name)})
        for metric_name, points in export["trends"].items():
            for point in points:
                writer.writerow({"metric": metric_name, "date": point["date"], "value": point["value"]})
        return FastAPIResponse(
            content=buffer.getvalue(), media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=quality-{org_id}.csv"},
        )

    return FastAPIResponse(
        content=json.dumps({"organization_id": str(org_id), **export}, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=quality-{org_id}.json"},
    )
