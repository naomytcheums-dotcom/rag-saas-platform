"""Partie 13.3 -- real alert-rule evaluation against real, already-live
data sources (Partie 11.5's admin_monitoring + Partie 13.1's HTTP
counter), real notification via email/webhook."""

import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.alerting import AlertChannel, AlertChannelType, AlertHistory, AlertOperator, AlertRule, Incident, IncidentStatus
from api.services.admin_monitoring import get_queue_status, get_resource_usage

logger = logging.getLogger(__name__)


class AlertingError(Exception):
    pass


class AlertRuleNotFoundError(AlertingError):
    pass


class AlertChannelNotFoundError(AlertingError):
    pass


class IncidentNotFoundError(AlertingError):
    pass


def real_metric_value(metric: str) -> float | None:
    """The honest, complete list of what this can actually check --
    real psutil/Celery data (Partie 11.5), not a fabricated number for
    a metric name nobody's wired a real source for."""
    if metric in ("cpu_percent", "memory_percent", "disk_percent"):
        usage = get_resource_usage()
        return usage.get(metric)
    if metric == "celery_queue_backlog":
        queue = get_queue_status()
        return float(queue["active_tasks"] + queue["reserved_tasks"])
    if metric == "http_5xx_total":
        from api.monitoring import HTTP_REQUESTS_TOTAL

        return float(sum(
            sample.value for m in HTTP_REQUESTS_TOTAL.collect() for sample in m.samples
            if sample.name.endswith("_total") and sample.labels.get("status_class") == "5xx"
        ))
    return None


def breaches(value: float, operator: AlertOperator, threshold: float) -> bool:
    return {
        AlertOperator.gt: value > threshold,
        AlertOperator.gte: value >= threshold,
        AlertOperator.lt: value < threshold,
        AlertOperator.lte: value <= threshold,
    }[operator]


async def send_alert_notification(channel: AlertChannel, message: str) -> bool:
    try:
        if channel.type == AlertChannelType.email:
            from api.services.email import send_security_alert_email

            send_security_alert_email(channel.config["email"], message)
        elif channel.type == AlertChannelType.webhook:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(channel.config["webhook_url"], json={"text": message})
                response.raise_for_status()
        return True
    except Exception:
        logger.warning("send_alert_notification: delivery failed for channel %s", channel.id, exc_info=True)
        return False


async def check_alert_rules(db: AsyncSession) -> list[AlertHistory]:
    """Real evaluation, real Celery-triggered (api/tasks/alerting.py).
    Returns the AlertHistory rows created for rules that breached this
    run -- an unmonitored metric (real_metric_value returns None) is
    silently skipped, not fabricated as 0."""
    rules = list((await db.scalars(select(AlertRule).where(AlertRule.enabled.is_(True)))).all())
    triggered = []
    for rule in rules:
        value = real_metric_value(rule.metric)
        if value is None or not breaches(value, rule.operator, rule.threshold):
            continue
        history = AlertHistory(
            rule_id=rule.id, value_at_trigger=value,
            message=f"Alert '{rule.name}': {rule.metric}={value} {rule.operator.value} {rule.threshold}",
        )
        db.add(history)
        await db.flush()
        if rule.channel_id:
            channel = await db.get(AlertChannel, rule.channel_id)
            if channel and channel.enabled:
                history.notified = await send_alert_notification(channel, history.message)
        triggered.append(history)
    await db.flush()
    return triggered


async def list_alert_rules(db: AsyncSession, organization_id: uuid.UUID | None) -> list[AlertRule]:
    return list((await db.scalars(select(AlertRule).where(AlertRule.organization_id == organization_id))).all())


async def create_alert_rule(db: AsyncSession, *, organization_id: uuid.UUID | None, name: str, metric: str, operator: AlertOperator, threshold: float, severity, channel_id: uuid.UUID | None, user_id: uuid.UUID | None) -> AlertRule:
    rule = AlertRule(organization_id=organization_id, name=name, metric=metric, operator=operator, threshold=threshold, severity=severity, channel_id=channel_id, created_by=user_id)
    db.add(rule)
    await db.flush()
    return rule


async def update_alert_rule(db: AsyncSession, rule_id: uuid.UUID, **fields) -> AlertRule:
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise AlertRuleNotFoundError(str(rule_id))
    for key, value in fields.items():
        if value is not None and hasattr(rule, key):
            setattr(rule, key, value)
    await db.flush()
    return rule


async def delete_alert_rule(db: AsyncSession, rule_id: uuid.UUID) -> None:
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise AlertRuleNotFoundError(str(rule_id))
    await db.delete(rule)
    await db.flush()


async def test_alert_rule(db: AsyncSession, rule_id: uuid.UUID) -> dict:
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise AlertRuleNotFoundError(str(rule_id))
    value = real_metric_value(rule.metric)
    return {"metric": rule.metric, "current_value": value, "would_trigger": value is not None and breaches(value, rule.operator, rule.threshold)}


async def list_alert_channels(db: AsyncSession, organization_id: uuid.UUID | None) -> list[AlertChannel]:
    return list((await db.scalars(select(AlertChannel).where(AlertChannel.organization_id == organization_id))).all())


async def create_alert_channel(db: AsyncSession, *, organization_id: uuid.UUID | None, name: str, type_: AlertChannelType, config: dict) -> AlertChannel:
    channel = AlertChannel(organization_id=organization_id, name=name, type=type_, config=config)
    db.add(channel)
    await db.flush()
    return channel


async def update_alert_channel(db: AsyncSession, channel_id: uuid.UUID, **fields) -> AlertChannel:
    channel = await db.get(AlertChannel, channel_id)
    if channel is None:
        raise AlertChannelNotFoundError(str(channel_id))
    for key, value in fields.items():
        if value is not None and hasattr(channel, key):
            setattr(channel, key, value)
    await db.flush()
    return channel


async def delete_alert_channel(db: AsyncSession, channel_id: uuid.UUID) -> None:
    channel = await db.get(AlertChannel, channel_id)
    if channel is None:
        raise AlertChannelNotFoundError(str(channel_id))
    await db.delete(channel)
    await db.flush()


async def get_alert_history(db: AsyncSession, organization_id: uuid.UUID | None, limit: int = 50) -> list[AlertHistory]:
    rule_ids = select(AlertRule.id).where(AlertRule.organization_id == organization_id)
    return list((await db.scalars(select(AlertHistory).where(AlertHistory.rule_id.in_(rule_ids)).order_by(AlertHistory.triggered_at.desc()).limit(limit))).all())


async def list_incidents(db: AsyncSession, organization_id: uuid.UUID | None, status_filter: IncidentStatus | None = None) -> list[Incident]:
    stmt = select(Incident).where(Incident.organization_id == organization_id)
    if status_filter is not None:
        stmt = stmt.where(Incident.status == status_filter)
    return list((await db.scalars(stmt.order_by(Incident.created_at.desc()))).all())


async def create_incident(db: AsyncSession, *, organization_id: uuid.UUID | None, title: str, description: str | None, severity, user_id: uuid.UUID | None) -> Incident:
    incident = Incident(organization_id=organization_id, title=title, description=description, severity=severity, created_by=user_id)
    db.add(incident)
    await db.flush()
    return incident


async def update_incident(db: AsyncSession, incident_id: uuid.UUID, **fields) -> Incident:
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise IncidentNotFoundError(str(incident_id))
    for key, value in fields.items():
        if value is not None and hasattr(incident, key):
            setattr(incident, key, value)
    await db.flush()
    return incident


async def resolve_incident(db: AsyncSession, incident_id: uuid.UUID) -> Incident:
    import datetime as dt

    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise IncidentNotFoundError(str(incident_id))
    incident.status = IncidentStatus.resolved
    incident.resolved_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return incident
