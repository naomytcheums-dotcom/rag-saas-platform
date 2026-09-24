"""Partie 20 -- advanced analytics endpoints.

Real, deliberate scoping decision (the spec's own literal paths had no
`{org_id}` anywhere, the same ambiguity Partie 18/19's own specs had --
resolved the same documented way): business metrics (revenue/customers/
retention/churn/ltv) are inherently platform-wide, matching
api/routers/admin_subscriptions.py's own real scope -- superadmin-only,
no org_id. Product and technical metrics, generic metrics query/export,
and dashboards are real per-organization concepts (an org's own usage,
its own events, its own LLM spend) -- kept under
`/organizations/{org_id}/analytics/...`, Member+ for reads, Admin+ for
writes, the same convention Partie 18/19 already established."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_superadmin
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.analytics import (
    CreateDashboardRequest, DashboardResponse, TrackEventRequest, UpdateDashboardRequest,
)
from api.security.permissions import require_permission
from api.security.organizations import require_org_admin, require_org_member
from api.services import analytics

router = APIRouter(tags=["analytics"])
org_router = APIRouter(prefix="/organizations/{org_id}/analytics", tags=["analytics"])


# -- Business (platform-wide, superadmin) -------------------------------------

@router.get("/analytics/business/revenue")
async def business_revenue_endpoint(date_range: str = Query("30d"), _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    from api.services.admin_subscriptions import get_revenue_stats
    return await get_revenue_stats(db)


@router.get("/analytics/business/customers")
async def business_customers_endpoint(_admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    return await analytics.get_customer_metrics(db)


@router.get("/analytics/business/retention")
async def business_retention_endpoint(date_range: str = Query("30d"), _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    days = analytics.parse_period(date_range)
    return await analytics.get_retention_rate(db, days=days)


@router.get("/analytics/business/churn")
async def business_churn_endpoint(date_range: str = Query("30d"), _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    days = analytics.parse_period(date_range)
    return await analytics.get_churn_rate(db, days=days)


@router.get("/analytics/business/ltv")
async def business_ltv_endpoint(date_range: str = Query("30d"), _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    days = analytics.parse_period(date_range)
    return await analytics.get_ltv(db, days=days)


@router.get("/analytics/business/revenue/trend")
async def business_revenue_trend_endpoint(date_range: str = Query("30d"), _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    days = analytics.parse_period(date_range)
    return await analytics.get_revenue_trend(db, days=days)


# -- Generic metrics (per-organization) ----------------------------------------

@org_router.post("/events", status_code=status.HTTP_201_CREATED)
async def track_event_endpoint(org_id: uuid.UUID, body: TrackEventRequest, caller: OrganizationMember = Depends(require_permission("audit_logs:read")), db: AsyncSession = Depends(get_db)):
    event = await analytics.track_event(db, org_id, user_id=caller.user_id, event_type=body.event_type, event_data=body.event_data)
    await db.commit()
    return {"id": str(event.id)} if event else {"tracked": False}


@org_router.get("/metrics")
async def get_metrics_endpoint(
    org_id: uuid.UUID, metric_name: str | None = None, period: str = "day", date_range: str = "30d",
    _caller: OrganizationMember = Depends(require_permission("audit_logs:read")), db: AsyncSession = Depends(get_db),
):
    return await analytics.get_metrics(db, org_id, metric_name=metric_name, period=period, date_range=date_range)


@org_router.get("/metrics/query")
async def query_metrics_endpoint(
    org_id: uuid.UUID, event_type: str | None = None, date_range: str = "30d",
    _caller: OrganizationMember = Depends(require_permission("audit_logs:read")), db: AsyncSession = Depends(get_db),
):
    return await analytics.query_metrics(db, org_id, event_type=event_type, date_range=date_range)


@org_router.get("/metrics/export")
async def export_metrics_endpoint(
    org_id: uuid.UUID, date_range: str = "30d", export_format: str = Query("json", alias="format"),
    _caller: OrganizationMember = Depends(require_permission("audit_logs:read")), db: AsyncSession = Depends(get_db),
):
    if export_format not in ("json", "csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="format must be 'json' or 'csv'")
    content, media_type = await analytics.export_metrics(db, org_id, date_range=date_range, export_format=export_format)
    extension = "csv" if export_format == "csv" else "json"
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename=analytics.{extension}"})


@org_router.get("/metrics/{metric_name}")
async def get_single_metric_endpoint(
    org_id: uuid.UUID, metric_name: str, period: str = "day", date_range: str = "30d",
    _caller: OrganizationMember = Depends(require_permission("audit_logs:read")), db: AsyncSession = Depends(get_db),
):
    return await analytics.get_metrics(db, org_id, metric_name=metric_name, period=period, date_range=date_range)


# -- Product (per-organization) -----------------------------------------------

@org_router.get("/product/usage")
async def product_usage_endpoint(org_id: uuid.UUID, date_range: str = "30d", _caller: OrganizationMember = Depends(require_permission("audit_logs:read")), db: AsyncSession = Depends(get_db)):
    return await analytics.get_product_usage(db, org_id, date_range=date_range)


@org_router.get("/product/adoption")
async def product_adoption_endpoint(org_id: uuid.UUID, date_range: str = "30d", _caller: OrganizationMember = Depends(require_permission("audit_logs:read")), db: AsyncSession = Depends(get_db)):
    return await analytics.get_product_adoption(db, org_id, date_range=date_range)


@org_router.get("/product/engagement")
async def product_engagement_endpoint(org_id: uuid.UUID, date_range: str = "30d", _caller: OrganizationMember = Depends(require_permission("audit_logs:read")), db: AsyncSession = Depends(get_db)):
    return await analytics.get_product_engagement(db, org_id, date_range=date_range)


@org_router.get("/product/funnels")
async def product_funnels_endpoint(
    org_id: uuid.UUID, steps: str = Query(..., description="Comma-separated event_type list, in order"), date_range: str = "30d",
    _caller: OrganizationMember = Depends(require_permission("audit_logs:read")), db: AsyncSession = Depends(get_db),
):
    step_list = [s.strip() for s in steps.split(",") if s.strip()]
    return await analytics.get_product_funnel(db, org_id, steps=step_list, date_range=date_range)


# -- Technical (per-organization) ----------------------------------------------

@org_router.get("/technical/performance")
async def technical_performance_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("audit_logs:manage")), db: AsyncSession = Depends(get_db)):
    return await analytics.get_technical_performance(db)


@org_router.get("/technical/errors")
async def technical_errors_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("audit_logs:manage")), db: AsyncSession = Depends(get_db)):
    return await analytics.get_technical_errors(db)


@org_router.get("/technical/api-usage")
async def technical_api_usage_endpoint(org_id: uuid.UUID, date_range: str = "30d", _caller: OrganizationMember = Depends(require_permission("audit_logs:manage")), db: AsyncSession = Depends(get_db)):
    return await analytics.get_product_usage(db, org_id, date_range=date_range)


@org_router.get("/technical/llm-usage")
async def technical_llm_usage_endpoint(org_id: uuid.UUID, date_range: str = "30d", _caller: OrganizationMember = Depends(require_permission("audit_logs:manage")), db: AsyncSession = Depends(get_db)):
    return await analytics.get_technical_llm_usage(db, org_id, date_range=date_range)


# -- Dashboards (per-organization) --------------------------------------------

@org_router.get("/dashboards", response_model=list[DashboardResponse])
async def list_dashboards_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("audit_logs:read")), db: AsyncSession = Depends(get_db)):
    return await analytics.list_dashboards(db, org_id)


@org_router.post("/dashboards", response_model=DashboardResponse, status_code=status.HTTP_201_CREATED)
async def create_dashboard_endpoint(org_id: uuid.UUID, body: CreateDashboardRequest, caller: OrganizationMember = Depends(require_permission("audit_logs:manage")), db: AsyncSession = Depends(get_db)):
    dashboard = await analytics.create_dashboard(db, org_id, name=body.name, widgets=body.widgets, is_default=body.is_default, user_id=caller.user_id)
    await db.commit()
    return dashboard


@org_router.get("/dashboards/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard_endpoint(org_id: uuid.UUID, dashboard_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("audit_logs:read")), db: AsyncSession = Depends(get_db)):
    try:
        return await analytics.get_dashboard(db, org_id, dashboard_id)
    except analytics.DashboardNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")


@org_router.patch("/dashboards/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard_endpoint(org_id: uuid.UUID, dashboard_id: uuid.UUID, body: UpdateDashboardRequest, caller: OrganizationMember = Depends(require_permission("audit_logs:manage")), db: AsyncSession = Depends(get_db)):
    try:
        dashboard = await analytics.update_dashboard(db, org_id, dashboard_id, data=body.model_dump(exclude_unset=True), user_id=caller.user_id)
    except analytics.DashboardNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")
    await db.commit()
    return dashboard


@org_router.delete("/dashboards/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard_endpoint(org_id: uuid.UUID, dashboard_id: uuid.UUID, caller: OrganizationMember = Depends(require_permission("audit_logs:manage")), db: AsyncSession = Depends(get_db)):
    try:
        await analytics.delete_dashboard(db, org_id, dashboard_id, caller.user_id)
    except analytics.DashboardNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")
    await db.commit()
