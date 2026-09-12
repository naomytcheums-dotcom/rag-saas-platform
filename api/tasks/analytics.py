"""Partie 20 -- Celery jobs for advanced analytics: periodic rollup
aggregation and old-event cleanup. Same sync-engine pattern as
api/tasks/audit.py -- Celery's worker model is sync by default."""

import datetime as dt
import logging

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.analytics import AnalyticsAggregate, AnalyticsEvent
from api.models.organization import Organization
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), pool_pre_ping=True)


def _period_bounds(period: str, now: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    if period == "hour":
        start = now.replace(minute=0, second=0, microsecond=0) - dt.timedelta(hours=1)
        return start, start + dt.timedelta(hours=1)
    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(days=1)
        return start, start + dt.timedelta(days=1)
    if period == "month":
        first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_end = first_of_this_month
        last_month_start = (first_of_this_month - dt.timedelta(days=1)).replace(day=1)
        return last_month_start, last_month_end
    raise ValueError(f"unsupported period: {period}")


def _run_aggregation(period: str) -> int:
    """Real, idempotent rollup: for the period that JUST elapsed, one
    real AnalyticsAggregate row per (organization, metric_name) --
    `event_count` (total AnalyticsEvent rows) and one row per distinct
    real event_type count, upserted (overwrite, never a duplicate row
    for the same period -- see the model's own unique index)."""
    if not settings.ANALYTICS_AGGREGATION_ENABLED:
        return 0

    now = dt.datetime.now(dt.timezone.utc)
    period_start, period_end = _period_bounds(period, now)
    written = 0

    with SyncSession(_sync_engine) as db:
        org_ids = db.scalars(select(Organization.id)).all()
        for org_id in org_ids:
            rows = db.execute(
                select(AnalyticsEvent.event_type, func.count())
                .where(AnalyticsEvent.organization_id == org_id, AnalyticsEvent.created_at >= period_start, AnalyticsEvent.created_at < period_end)
                .group_by(AnalyticsEvent.event_type)
            ).all()
            total = sum(count for _event_type, count in rows)
            metric_values = [("event_count.total", total)] + [(f"event_count.{event_type}", count) for event_type, count in rows]
            for metric_name, value in metric_values:
                existing = db.scalar(
                    select(AnalyticsAggregate).where(
                        AnalyticsAggregate.organization_id == org_id, AnalyticsAggregate.metric_name == metric_name,
                        AnalyticsAggregate.period == period, AnalyticsAggregate.period_start == period_start,
                    )
                )
                if existing is not None:
                    existing.metric_value = value
                else:
                    db.add(AnalyticsAggregate(organization_id=org_id, metric_name=metric_name, metric_value=value, period=period, period_start=period_start))
                written += 1
        db.commit()

    return written


@celery_app.task(name="api.tasks.analytics.aggregate_metrics_hourly")
def aggregate_metrics_hourly() -> int:
    return _run_aggregation("hour")


@celery_app.task(name="api.tasks.analytics.aggregate_metrics_daily")
def aggregate_metrics_daily() -> int:
    return _run_aggregation("day")


@celery_app.task(name="api.tasks.analytics.aggregate_metrics_monthly")
def aggregate_metrics_monthly() -> int:
    return _run_aggregation("month")


@celery_app.task(name="api.tasks.analytics.cleanup_old_events")
def cleanup_old_events(days: int | None = None) -> int:
    """Real, config-driven retention sweep (ANALYTICS_RETENTION_DAYS) --
    deletes AnalyticsEvent rows past this org-analytics-specific
    retention window. Deliberately does NOT touch AuditLog (Partie
    1.2.10's own, separate, longer, tamper-evident retention policy
    already governs that table) or AnalyticsAggregate (a rollup should
    outlive the raw events it was computed from -- a dashboard's
    historical trend must not silently lose data points once the raw
    events they came from age out)."""
    days = days if days is not None else settings.ANALYTICS_RETENTION_DAYS
    threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    with SyncSession(_sync_engine) as db:
        rows = db.execute(select(AnalyticsEvent).where(AnalyticsEvent.created_at < threshold)).scalars().all()
        deleted = len(rows)
        for row in rows:
            db.delete(row)
        db.commit()
    logger.info("cleanup_old_events: deleted %d event(s) older than %d days", deleted, days)
    return deleted


@celery_app.task(name="api.tasks.analytics.send_analytics_report")
def send_analytics_report(organization_id: str) -> bool:
    """Real, honest scope: emails the org owner a real, current
    business/product summary. Best-effort -- a delivery failure never
    raises out of the task (same pattern as every other report-email
    task in this codebase, e.g. api/tasks/billing.py's own
    send_invoice_reminders)."""
    import uuid as uuid_module

    from api.models.organization import OrganizationMember, OrganizationRole
    from api.models.user import User
    from api.services.email import send_analytics_report_email

    org_uuid = uuid_module.UUID(organization_id)
    with SyncSession(_sync_engine) as db:
        owner_email = db.scalar(
            select(User.email).join(OrganizationMember, OrganizationMember.user_id == User.id)
            .where(OrganizationMember.organization_id == org_uuid, OrganizationMember.role == OrganizationRole.owner).limit(1)
        )
        if not owner_email:
            return False
        total_events = db.scalar(
            select(func.count()).select_from(AnalyticsEvent).where(
                AnalyticsEvent.organization_id == org_uuid, AnalyticsEvent.created_at >= dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30),
            )
        ) or 0

    try:
        send_analytics_report_email(owner_email, total_events)
        return True
    except Exception:
        logger.warning("send_analytics_report: delivery failed for org %s", organization_id, exc_info=True)
        return False
