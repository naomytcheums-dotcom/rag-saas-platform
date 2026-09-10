"""Partie 13.3 -- periodic real alert-rule evaluation. Sync engine, same
pattern as every other Celery task module in this project."""

import asyncio
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.services.alerting import breaches, real_metric_value
from api.models.alerting import AlertChannel, AlertHistory, AlertRule
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), pool_pre_ping=True)


@celery_app.task(name="api.tasks.alerting.check_alert_rules")
def check_alert_rules_task() -> int:
    if not settings.ALERTING_ENABLED:
        return 0

    triggered = 0
    with SyncSession(_sync_engine) as db:
        rules = db.query(AlertRule).filter(AlertRule.enabled.is_(True)).all()
        for rule in rules:
            value = real_metric_value(rule.metric)
            if value is None or not breaches(value, rule.operator, rule.threshold):
                continue
            history = AlertHistory(
                rule_id=rule.id, value_at_trigger=value,
                message=f"Alert '{rule.name}': {rule.metric}={value} {rule.operator.value} {rule.threshold}",
            )
            db.add(history)
            db.flush()
            if rule.channel_id:
                channel = db.get(AlertChannel, rule.channel_id)
                if channel and channel.enabled:
                    from api.services.alerting import send_alert_notification

                    history.notified = asyncio.run(send_alert_notification(channel, history.message))
            triggered += 1
        db.commit()

    logger.info("check_alert_rules: %d rule(s) triggered", triggered)
    return triggered
