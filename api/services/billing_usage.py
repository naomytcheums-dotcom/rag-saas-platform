"""
Partie 12.3 -- usage breakdown/forecast/alerts, built entirely on top of
the real, pre-existing api/security/usage.py ledger (Partie 1.3.8) and
Plan's real max_* limits (api/models/admin.py, Partie 11.4/12.1). No new
usage-counting table -- see api/models/billing.py's module docstring
for why that would duplicate real, already-working machinery.
"""

import datetime as dt
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.billing import UsageAlert
from api.security.usage import get_usage, get_usage_summary, record_usage


def _aware(moment: dt.datetime) -> dt.datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=dt.timezone.utc)


def subscription_grants_paid_access(sub: Subscription, now: dt.datetime | None = None) -> bool:
    """BILL-007 -- whether a subscription still entitles its organization to its (paid) plan.

    Access follows what the provider reported, not just the stored plan: a canceled subscription keeps its plan only until the
    paid period ends, a past-due one only for `BILLING_GRACE_PERIOD_DAYS` after the period end, and a `pending` (incomplete) one never.
    Without a known period end (self-hosted/dev, manually assigned plans) the stored status decides, so nothing changes there."""
    now = now or dt.datetime.now(dt.timezone.utc)
    period_end = _aware(sub.current_period_end) if sub.current_period_end else None
    grace = dt.timedelta(days=max(settings.BILLING_GRACE_PERIOD_DAYS, 0))
    if sub.status == SubscriptionStatus.pending:
        return False
    if sub.status == SubscriptionStatus.canceled:
        return period_end is not None and now <= period_end
    if sub.status == SubscriptionStatus.past_due:
        return period_end is None or now <= period_end + grace
    return period_end is None or now <= period_end + grace


async def get_effective_plan(db: AsyncSession, organization_id: uuid.UUID) -> Plan | None:
    """The plan whose limits and features apply to the organization right now.

    An organization that has no subscription row yet (a subscription is created the first time its billing page is read, not when the organization is created) is
    on the deployment's default plan (`BILLING_DEFAULT_PLAN`, "free" unless a self-hosted deployment chooses otherwise): before this rule such an organization had
    NO limit at all, which let any new account upload documents and ask questions past the Free plan until someone opened the billing page."""
    sub = await db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
    if sub is None:
        from api.services.admin_subscriptions import ensure_free_plan_seeded

        key = (settings.BILLING_DEFAULT_PLAN or "free").strip() or "free"
        default_plan = await db.scalar(select(Plan).where(Plan.key == key)) if key != "free" else None
        return default_plan or await ensure_free_plan_seeded(db)
    plan = await db.get(Plan, sub.plan_id)
    if plan is None or ((plan.monthly_price_cents or 0) <= 0 and (plan.yearly_price_cents or 0) <= 0):
        return plan
    if subscription_grants_paid_access(sub):
        return plan
    return await db.scalar(select(Plan).where(Plan.key == "free")) or plan

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

    plan = await get_effective_plan(db, organization_id)
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


async def check_plan_resource_limit(db: AsyncSession, organization_id: uuid.UUID, resource_type: str) -> tuple[bool, int | None, int | None]:
    """Partie 16 (bis) -- real SaaS plan enforcement: a direct COUNT of
    the real resource row (documents/agents/members) against the real
    Plan.max_* column, not the usage ledger above (which nothing
    populates for these specific metrics today -- counting the real
    rows directly is more honest than gating on a number nobody writes
    yet). Returns (within_limit, current_count, limit) -- limit is None
    for an unlimited plan (Enterprise), current_count is None if
    resource_type isn't a real, gated resource."""
    from api.models.agent import Agent
    from api.models.document import Document
    from api.models.organization import OrganizationMember

    plan = await get_effective_plan(db, organization_id)
    if plan is None:
        return True, None, None

    if resource_type == "documents":
        limit = plan.max_documents
        count = await _live_document_count(db, organization_id)
    elif resource_type == "agents":
        limit = plan.max_agents
        count = await db.scalar(select(func.count()).select_from(Agent).where(Agent.organization_id == organization_id, Agent.deleted_at.is_(None)))
    elif resource_type == "members":
        limit = plan.max_members
        count = await db.scalar(select(func.count()).select_from(OrganizationMember).where(OrganizationMember.organization_id == organization_id))
    else:
        return True, None, None

    count = count or 0
    if limit is None:
        return True, count, None

    # Phase 5, Étape 21 -- real notification triggers for plan quota
    # (billing_quota_warning at 80%, billing_quota_exceeded at 100%).
    # Never blocks the check itself -- a notification failure must never
    # break the real quota enforcement.
    try:
        from api.services.notifications import (
            notify_billing_quota_exceeded,
            notify_billing_quota_warning,
        )
        ratio = count / limit if limit > 0 else 0
        if ratio >= 1.0:
            await notify_billing_quota_exceeded(db, organization_id, float(count), float(limit))
        elif ratio >= 0.8:
            await notify_billing_quota_warning(db, organization_id, float(count), float(limit))
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(
            "check_plan_resource_limit: could not notify for org '%s' (%s): %s",
            organization_id, resource_type, exc,
        )

    return count < limit, count, limit


async def _live_document_count(db: AsyncSession, organization_id: uuid.UUID) -> int:
    """Documents that count against the plan: a document in the trash (`deleted_at` set) frees its slot, exactly as it frees its storage."""
    from api.models.document import Document

    return int(await db.scalar(select(func.count()).select_from(Document).where(Document.organization_id == organization_id, Document.deleted_at.is_(None))) or 0)


class DocumentLimitExceededError(Exception):
    """The organization's plan allows no further document. Deliberately NOT a ValueError: the routes map ValueError to 400 (bad input), this is a 402 (plan limit),
    answered by one application-wide handler (api/main.py)."""

    def __init__(self, limit: int, count: int) -> None:
        super().__init__(f"This organization's plan allows {limit} documents (currently {count}). Upgrade the plan to add more.")
        self.limit = limit
        self.count = count


async def _serialize_per_organization(db: AsyncSession, organization_id: uuid.UUID, scope: str) -> None:
    """On PostgreSQL, a transaction-scoped advisory lock keyed on (scope, organization): two concurrent requests that both check "is there a free slot?" are
    executed one after the other, so the last slot cannot be handed out twice. The lock is released at commit/rollback. No-op elsewhere (SQLite is single-writer)."""
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": f"{scope}:{organization_id}"})


async def ensure_document_slot(db: AsyncSession, organization_id: uuid.UUID, additional: int = 1) -> None:
    """Call right before a `Document` row is created, on EVERY path that creates one (upload, batch, URL/sitemap/GitHub/Drive/Notion/Confluence/OneDrive/ZIP import,
    public API, integrations, CRM, batch jobs): raises `DocumentLimitExceededError` when the effective plan has no room for `additional` more documents.
    Unlimited plans (`max_documents IS NULL`) and organizations without any subscription are never refused."""
    plan = await get_effective_plan(db, organization_id)
    if plan is None or plan.max_documents is None:
        return
    await _serialize_per_organization(db, organization_id, "documents")
    count = await _live_document_count(db, organization_id)
    if count + additional > plan.max_documents:
        raise DocumentLimitExceededError(plan.max_documents, count)


QUESTION_LIMIT_ERROR_PREFIX = "Daily question limit reached"
# Error text of a run refused because the organization cannot pay for it (credits, spend cap) or exhausted its plan: the HTTP layers answer 402 for these.
PAYMENT_REQUIRED_RUN_ERRORS = ("Insufficient AI credits", "Spend cap exceeded", QUESTION_LIMIT_ERROR_PREFIX)


class QuestionLimitExceededError(Exception):
    """The plan's number of questions per UTC day is used up."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"{QUESTION_LIMIT_ERROR_PREFIX}: this organization's plan allows {limit} questions per day and today's quota is used up. It resets at 00:00 UTC; upgrade the plan for more.")
        self.limit = limit


QUESTIONS_METRIC = "questions"


async def reserve_daily_question(db: AsyncSession, organization_id: uuid.UUID, *, user_id: uuid.UUID | None = None) -> None:
    """Counts one question against the effective plan's `max_questions_per_day` (UTC day) and raises `QuestionLimitExceededError` when the day's quota is used up.

    The counter is the usage ledger's own daily row (`organization_usage`, metric "questions", the number the usage page shows). The increment is a single atomic
    `INSERT ... ON CONFLICT DO UPDATE ... WHERE value < limit`, so two concurrent questions cannot both take the last slot. The counting is part of the caller's
    transaction (not committed here); callers invoke it AFTER the cheaper refusals (insufficient credits), so a refused question does not use the quota.
    `max_questions_per_day IS NULL` (Pro, Business, Enterprise) means unlimited: the question is still recorded for the usage page."""
    from api.models.organization_usage import OrganizationUsage, OrganizationUsageDetail

    plan = await get_effective_plan(db, organization_id)
    limit = plan.max_questions_per_day if plan is not None else None
    if limit is None:
        await record_usage(db, organization_id, QUESTIONS_METRIC, 1, user_id=user_id)
        return

    if limit <= 0:
        raise QuestionLimitExceededError(limit)
    today = dt.datetime.now(dt.timezone.utc).date()
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    else:
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
    statement = dialect_insert(OrganizationUsage).values(id=uuid.uuid4(), organization_id=organization_id, date=today, metric=QUESTIONS_METRIC, value=1)
    statement = statement.on_conflict_do_update(
        index_elements=[OrganizationUsage.organization_id, OrganizationUsage.date, OrganizationUsage.metric],
        set_={"value": OrganizationUsage.value + 1}, where=OrganizationUsage.value < limit,
    ).returning(OrganizationUsage.value)
    taken = (await db.execute(statement)).scalar_one_or_none()
    if taken is None:
        raise QuestionLimitExceededError(limit)
    db.add(OrganizationUsageDetail(organization_id=organization_id, user_id=user_id, metric=QUESTIONS_METRIC, value=1))
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
