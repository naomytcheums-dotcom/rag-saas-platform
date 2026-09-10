"""
Partie 12.3 -- usage breakdown/forecast/alerts, built entirely on top of
the real, pre-existing api/security/usage.py ledger (Partie 1.3.8) and
Plan's real max_* limits (api/models/admin.py, Partie 11.4/12.1). No new
usage-counting table -- see api/models/billing.py's module docstring
for why that would duplicate real, already-working machinery.
"""

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.admin import Plan, Subscription
from api.models.billing import UsageAlert
from api.security.usage import get_usage, get_usage_summary

# Metric -> the Plan column that caps it. Only metrics this codebase
# actually has a real Plan limit for are checked -- an unlisted metric
# (e.g. "tokens_input", which Partie 9's real /v1/chat doesn't exist
# yet to emit) simply can't be limit-checked, honestly, rather than
# pretending a limit exists for it.
_METRIC_TO_PLAN_LIMIT = {
    "documents_processed": "max_documents",
    "agents_created": "max_agents",
    "members_invited": "max_members",
    "api_requests": "max_requests_per_month",
}


class LimitExceededError(Exception):
    pass


async def check_limits(db: AsyncSession, organization_id: uuid.UUID, resource_type: str, amount: int = 1) -> bool:
    """True if consuming `amount` more of `resource_type` this month
    stays within the organization's real plan limit. A metric with no
    known Plan column, or a plan with no cap set for it (None = truly
    unlimited, e.g. Enterprise), always returns True."""
    limit_attr = _METRIC_TO_PLAN_LIMIT.get(resource_type)
    if limit_attr is None:
        return True

    sub = await db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
    if sub is None:
        return True
    plan = await db.get(Plan, sub.plan_id)
    limit = getattr(plan, limit_attr, None) if plan else None
    if limit is None:
        return True

    today = dt.datetime.now(dt.timezone.utc).date()
    month_start = today.replace(day=1)
    used = await get_usage(db, organization_id, resource_type, start_date=month_start, end_date=today)
    return (used + amount) <= limit


async def get_usage_breakdown(db: AsyncSession, organization_id: uuid.UUID, period_days: int = 30) -> dict:
    end = dt.datetime.now(dt.timezone.utc).date()
    start = end - dt.timedelta(days=period_days)
    return await get_usage_summary(db, organization_id, start_date=start, end_date=end)


async def get_usage_forecast(db: AsyncSession, organization_id: uuid.UUID, months: int = 1) -> dict:
    """A real, simple linear projection from the last 30 real days of
    usage -- not a machine-learning forecast, honestly labelled as
    such: `projected_next_period` is today's real daily average times
    30, nothing more."""
    end = dt.datetime.now(dt.timezone.utc).date()
    start = end - dt.timedelta(days=30)
    summary = await get_usage_summary(db, organization_id, start_date=start, end_date=end)
    days_elapsed = max((end - start).days, 1)
    projected = {metric: round((total / days_elapsed) * 30 * months) for metric, total in summary["total_by_metric"].items()}
    return {"based_on_days": days_elapsed, "projected_next_period": projected}


async def list_usage_alerts(db: AsyncSession, organization_id: uuid.UUID) -> list[UsageAlert]:
    return list((await db.scalars(select(UsageAlert).where(UsageAlert.organization_id == organization_id))).all())


async def create_usage_alert(db: AsyncSession, organization_id: uuid.UUID, *, resource_type: str, threshold_percent: int, user_id: uuid.UUID | None) -> UsageAlert:
    alert = UsageAlert(organization_id=organization_id, resource_type=resource_type, threshold_percent=threshold_percent, created_by=user_id)
    db.add(alert)
    await db.flush()
    return alert


async def delete_usage_alert(db: AsyncSession, organization_id: uuid.UUID, alert_id: uuid.UUID) -> None:
    alert = await db.get(UsageAlert, alert_id)
    if alert is None or alert.organization_id != organization_id:
        raise ValueError("alert not found")
    await db.delete(alert)
    await db.flush()


async def check_usage_alerts(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    """Which of this organization's configured alerts are currently
    breached, checked against the real limit each references."""
    alerts = await list_usage_alerts(db, organization_id)
    if not alerts:
        return []
    sub = await db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
    plan = await db.get(Plan, sub.plan_id) if sub else None

    today = dt.datetime.now(dt.timezone.utc).date()
    month_start = today.replace(day=1)
    triggered = []
    for alert in alerts:
        limit_attr = _METRIC_TO_PLAN_LIMIT.get(alert.resource_type)
        limit = getattr(plan, limit_attr, None) if (plan and limit_attr) else None
        if not limit:
            continue
        used = await get_usage(db, organization_id, alert.resource_type, start_date=month_start, end_date=today)
        percent = round((used / limit) * 100)
        if percent >= alert.threshold_percent:
            triggered.append({"resource_type": alert.resource_type, "threshold_percent": alert.threshold_percent, "current_percent": percent, "used": used, "limit": limit})
    return triggered
