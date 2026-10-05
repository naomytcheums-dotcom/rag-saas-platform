"""Partie 13.3 -- real alert-rule evaluation against real, already-live
data sources (Partie 11.5's admin_monitoring + Partie 13.1's HTTP
counter), real notification via email/webhook."""

import asyncio
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.alerting import AlertChannel, AlertChannelType, AlertHistory, AlertOperator, AlertRule, Incident, IncidentStatus
from api.models.evaluation import EvaluationDataset, EvaluationJob, EvaluationJobStatus, EvaluationResult
from api.services.admin_monitoring import get_queue_status, get_resource_usage
from api.services.url_fetching import ssrf_safe_client

logger = logging.getLogger(__name__)

# Hardening Mission (§13, Guardian) -- the real RAG-quality metric names
# `api/services/evaluation_results.py::extend_evaluation_metrics` actually
# produces on every real `EvaluationResult.metrics` row -- the exact
# same keys this project's own AGENTS.md ("Mode 2 — GUARDIAN") already
# names with real default thresholds (Recall@5 < 0.80 WARNING,
# MRR < 0.75 WARNING, NDCG < 0.70 WARNING, taux d'hallucination > 0.10
# WARNING). Listed explicitly rather than accepting any string, so a
# typo'd `AlertRule.metric` fails honestly (`real_metric_value` returns
# `None`, the rule is silently skipped, same convention as an
# unmonitored infra metric) instead of a confusing empty-average.
_RAG_QUALITY_METRICS = {
    "recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10",
    "mrr", f"ndcg_at_{settings.NDCG_DEFAULT_K}", "hallucination_rate",
}
# Public name (api/routers/quality_alerts.py validates tenant-created rules against it).
RAG_QUALITY_METRICS = _RAG_QUALITY_METRICS


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


async def _latest_completed_job_id(db: AsyncSession, organization_id: uuid.UUID) -> uuid.UUID | None:
    return await db.scalar(
        select(EvaluationJob.id)
        .join(EvaluationDataset, EvaluationDataset.id == EvaluationJob.dataset_id)
        .where(EvaluationDataset.organization_id == organization_id, EvaluationJob.status == EvaluationJobStatus.completed)
        .order_by(EvaluationJob.completed_at.desc())
        .limit(1)
    )


async def explain_rag_quality_alert(db: AsyncSession, metric: str, organization_id: uuid.UUID | None) -> str | None:
    """Hardening Mission (§13, Guardian) -- the "explain" and "propose an
    action" steps of detect -> explain -> alert -> propose. For a breached
    RAG-quality metric, runs the Autopsy tally (`categorize_job_failures`:
    retrieval / generation / other from real failure rows, plus hallucination
    from the real measured rate) over the SAME job the metric was averaged
    from, and names the next real step. Deterministic and data-driven: the
    suggestion follows the dominant measured cause, and it only ever
    SUGGESTS -- applying a change stays an explicit, audited, human action
    (`POST .../agents/{id}/retrieval-config/apply`)."""
    if metric not in _RAG_QUALITY_METRICS or organization_id is None:
        return None
    job_id = await _latest_completed_job_id(db, organization_id)
    if job_id is None:
        return None

    from api.services.evaluation_jobs import categorize_job_failures

    counts = await categorize_job_failures(db, job_id)
    retrieval, generation, hallucination, other = (counts.get(k, 0) for k in ("retrieval", "generation", "hallucination", "other"))
    summary = f"Autopsy of job {job_id}: retrieval={retrieval}, generation={generation}, hallucination={hallucination}, other={other}."

    if metric == "hallucination_rate":
        action = (
            "answers are not grounded in the retrieved context: enable context compression, require citations, "
            "lower the temperature or tighten the system prompt, then re-run the benchmark"
            if hallucination else "no individual hallucination was flagged: inspect the judged answers of this job before changing anything"
        )
    elif retrieval and retrieval >= max(generation, hallucination, other):
        action = (
            f"retrieval failures dominate: run POST /organizations/{organization_id}/evolution/retrieval/run to test a wider top_k, "
            "reranking or MMR against this baseline, and apply a candidate only if it is accepted (no regression on the guard metrics)"
        )
    elif generation or hallucination:
        action = "retrieval is not the dominant cause: review the model, prompt and context size before touching retrieval settings"
    else:
        action = (
            "no failure rows were recorded, so the metric is low without errors (relevant documents ranked too low): "
            f"run POST /organizations/{organization_id}/evolution/retrieval/run to test candidates"
        )
    return f"{summary} Suggested action: {action}."


async def real_rag_quality_metric_value(db: AsyncSession, metric: str, organization_id: uuid.UUID | None) -> float | None:
    """Hardening Mission (§13, Guardian) -- the real, organization-scoped
    counterpart to `real_metric_value` above, for the RAG-quality
    metrics (`_RAG_QUALITY_METRICS`) no infra counter can answer.
    Averages the REAL, already-computed `EvaluationResult.metrics`
    values across every result of this organization's most recently
    COMPLETED `EvaluationJob` (across any of its datasets) -- the exact
    real signal AGENTS.md's own "Mode 2 — GUARDIAN" describes
    (`run_eval_benchmark -> Recall@5 = 0.72`). Returns `None` (never a
    fabricated 0 or 1) when this metric name isn't a real RAG-quality
    one, no organization is given, no evaluation job has ever completed
    for it, or the completed job's own results genuinely never computed
    this particular metric (e.g. hallucination_rate needs a configured
    judge LLM -- see that metric's own real, documented reliability
    flag)."""
    if metric not in _RAG_QUALITY_METRICS or organization_id is None:
        return None

    latest_job_id = await _latest_completed_job_id(db, organization_id)
    if latest_job_id is None:
        return None

    # Real average over a real JSON field's own key -- Postgres and
    # SQLite both support `->>'key'` JSON extraction via SQLAlchemy's
    # generic JSON comparator (`element.as_float()`, same real,
    # value-type-aware cast `api.services.metadata_filtering` already
    # established), so this stays correct against both the fast test
    # suite's SQLite backend and real production Postgres without two
    # divergent query paths.
    value = await db.scalar(
        select(func.avg(EvaluationResult.metrics[metric].as_float()))
        .where(EvaluationResult.evaluation_job_id == latest_job_id, EvaluationResult.metrics[metric].as_float().is_not(None))
    )
    return float(value) if value is not None else None


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

            await asyncio.to_thread(send_security_alert_email, channel.config["email"], message)
        elif channel.type == AlertChannelType.webhook:
            # Phase 4, Étape 4 (SSRF Hardening Extension) -- real, genuine
            # fix: `channel.config["webhook_url"]` is admin-configured
            # (`POST /alerting/channels`, `require_admin`) with no real
            # SSRF protection at all -- reuses the SAME real, canonical,
            # DNS-rebinding-safe transport `url_fetching.py` already
            # built, never a second, weaker one.
            async with ssrf_safe_client(timeout=10.0) as client:
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
        # Hardening Mission (§13, Guardian) -- a real RAG-quality metric
        # (e.g. "recall_at_5") is organization-scoped and needs a real
        # DB lookup; an infra metric (cpu_percent, etc.) doesn't. Tried
        # in that order so a rule accidentally named after both an infra
        # AND a RAG-quality metric (impossible today, but never silently
        # ambiguous) always prefers the real, per-organization signal.
        value = await real_rag_quality_metric_value(db, rule.metric, rule.organization_id)
        if value is None:
            value = real_metric_value(rule.metric)
        if value is None or not breaches(value, rule.operator, rule.threshold):
            continue
        message = f"Alert '{rule.name}': {rule.metric}={value} {rule.operator.value} {rule.threshold}"
        explanation = await explain_rag_quality_alert(db, rule.metric, rule.organization_id)
        if explanation:
            message = f"{message}. {explanation}"
        history = AlertHistory(rule_id=rule.id, value_at_trigger=value, message=message)
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
    value = await real_rag_quality_metric_value(db, rule.metric, rule.organization_id)
    if value is None:
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
