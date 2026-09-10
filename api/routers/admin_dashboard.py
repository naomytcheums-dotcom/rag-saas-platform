"""
Partie 11.1/11.5/11.6 -- global platform stats, system health/
monitoring, and system logs. All global (require_admin), not org-
scoped -- an admin dashboard reads across every organization, unlike
Partie 10's Security screen.
"""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_admin, require_superadmin
from api.models.user import User
from api.schemas.admin_dashboard import (
    GlobalStatsResponse,
    LogsStatsResponse,
    QueueStatusResponse,
    ResourceUsageResponse,
    SystemHealthResponse,
    SystemLogListResponse,
    SystemLogResponse,
)
from api.services.admin_logs import get_log_sources, get_logs_stats, get_system_log, list_system_logs, purge_old_system_logs
from api.services.admin_monitoring import get_queue_status, get_resource_usage, get_system_health
from api.services.admin_stats import (
    get_api_usage_stats,
    get_conversation_stats,
    get_document_stats,
    get_global_stats,
    get_organization_stats,
    get_user_stats,
)
from api.services.admin_subscriptions import get_revenue_stats

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


@router.get("/stats", response_model=GlobalStatsResponse)
async def get_stats_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return GlobalStatsResponse(**await get_global_stats(db))


@router.get("/stats/users")
async def get_user_stats_endpoint(days: int = 30, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await get_user_stats(db, days)


@router.get("/stats/organizations")
async def get_organization_stats_endpoint(days: int = 30, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await get_organization_stats(db, days)


@router.get("/stats/revenue")
async def get_revenue_stats_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await get_revenue_stats(db)


@router.get("/stats/api-usage")
async def get_api_usage_stats_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await get_api_usage_stats(db)


@router.get("/stats/conversations")
async def get_conversation_stats_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await get_conversation_stats(db)


@router.get("/stats/documents")
async def get_document_stats_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await get_document_stats(db)


@router.get("/monitoring/health", response_model=SystemHealthResponse)
async def get_monitoring_health_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return SystemHealthResponse(**await get_system_health(db))


@router.get("/monitoring/resources", response_model=ResourceUsageResponse)
async def get_monitoring_resources_endpoint(_admin: User = Depends(require_admin)):
    return ResourceUsageResponse(**get_resource_usage())


@router.get("/monitoring/queues", response_model=QueueStatusResponse)
async def get_monitoring_queues_endpoint(_admin: User = Depends(require_admin)):
    return QueueStatusResponse(**get_queue_status())


@router.get("/logs", response_model=SystemLogListResponse)
async def list_logs_endpoint(
    level: str | None = None, logger_name: str | None = None, search: str | None = None, since: dt.datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    rows, total = await list_system_logs(db, level=level, logger_name=logger_name, search=search, since=since, limit=limit, offset=offset)
    return SystemLogListResponse(items=[SystemLogResponse.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/logs/stats", response_model=LogsStatsResponse)
async def get_logs_stats_endpoint(days: int = 7, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return LogsStatsResponse(**await get_logs_stats(db, days))


@router.get("/logs/sources")
async def get_log_sources_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return {"sources": await get_log_sources(db)}


@router.get("/logs/levels")
async def get_log_levels_endpoint(_admin: User = Depends(require_admin)):
    return {"levels": ["WARNING", "ERROR", "CRITICAL"]}


@router.get("/logs/export")
async def export_logs_endpoint(fmt: str = "json", _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from fastapi.responses import Response

    rows, _ = await list_system_logs(db, limit=10000, offset=0)
    if fmt == "csv":
        import csv
        import io

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["id", "level", "logger_name", "message", "created_at"])
        for row in rows:
            writer.writerow([row.id, row.level, row.logger_name, row.message, row.created_at.isoformat()])
        return Response(content=buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=system-logs.csv"})
    import json as json_module

    return Response(content=json_module.dumps([SystemLogResponse.model_validate(r).model_dump(mode="json") for r in rows]), media_type="application/json")


@router.get("/activity")
async def get_recent_activity_endpoint(limit: int = Query(default=50, ge=1, le=200), _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Partie 11.1 -- real, additive alias over the already-existing
    GET /admin/audit-logs (api/routers/audit.py) -- the platform's own
    real audit trail IS its real recent-activity feed; not a second,
    duplicate log."""
    from api.routers.audit import _list_audit_logs

    return await _list_audit_logs(db, user_id=None, action=None, since=None, until=None, limit=limit, offset=0)


@router.get("/alerts")
async def get_admin_alerts_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Real, additive alias over Partie 10.5's SecurityAlert table,
    platform-wide (every organization's active alerts) rather than
    scoped to one -- the same real alerts the Security screen dismisses
    per-organization."""
    from sqlalchemy import select

    from api.models.security_scan import SecurityAlert

    rows = (await db.scalars(select(SecurityAlert).where(SecurityAlert.dismissed_at.is_(None)).order_by(SecurityAlert.created_at.desc()).limit(50))).all()
    return [{"id": str(r.id), "organization_id": str(r.organization_id) if r.organization_id else None, "message": r.message, "severity": r.severity.value, "created_at": r.created_at} for r in rows]


@router.get("/logs/{log_id}", response_model=SystemLogResponse)
async def get_log_endpoint(log_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    log = await get_system_log(db, log_id)
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return SystemLogResponse.model_validate(log)


@router.delete("/logs/purge")
async def purge_logs_endpoint(older_than_days: int = Query(ge=1), _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    deleted = await purge_old_system_logs(db, older_than_days)
    await db.commit()
    return {"deleted": deleted}
