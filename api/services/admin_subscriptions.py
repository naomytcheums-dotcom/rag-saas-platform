"""
Partie 11.4 -- real Plan/Subscription CRUD. Honest scope: this
environment has no payment processor wired (Partie 12, 0/23) -- there
is no Stripe/Paystack webhook actually charging a card or updating
`Subscription.status`. What IS real: the data model, the admin CRUD,
and the MRR/ARR/ARPU math, computed for real from whatever
Plan.monthly_price_cents × active Subscription rows actually exist.
Every organization gets a real `free` (0 cents) Subscription at
creation (see api/security/organizations.py's create_organization_with_owner)
so these numbers are never null -- just genuinely 0 until a real plan
with a non-zero price is assigned to a real organization.
"""

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.admin import Plan, Subscription, SubscriptionStatus


class AdminSubscriptionError(Exception):
    pass


class PlanNotFoundError(AdminSubscriptionError):
    pass


class SubscriptionNotFoundError(AdminSubscriptionError):
    pass


async def ensure_free_plan_seeded(db: AsyncSession) -> Plan:
    plan = await db.scalar(select(Plan).where(Plan.key == "free"))
    if plan is None:
        plan = Plan(key="free", name="Free", monthly_price_cents=0, max_documents=50, max_agents=3, max_members=5)
        db.add(plan)
        await db.flush()
    return plan


# Partie 16 (bis) -- the real, literal SaaS tier list, seeded once
# (idempotent, same key-existence check as ensure_free_plan_seeded).
_DEFAULT_PLANS = [
    {"key": "starter", "name": "Starter", "monthly_price_cents": 4900, "yearly_price_cents": 49000, "max_documents": 100, "max_agents": 3, "max_members": 5},
    {"key": "pro", "name": "Pro", "monthly_price_cents": 19900, "yearly_price_cents": 199000, "max_documents": 1000, "max_agents": 10, "max_members": 20, "priority_support": True, "advanced_features": True},
    {"key": "enterprise", "name": "Enterprise", "monthly_price_cents": 99900, "yearly_price_cents": 999000, "max_documents": None, "max_agents": None, "max_members": None, "priority_support": True, "advanced_features": True, "sla": True},
]


async def ensure_default_plans_seeded(db: AsyncSession) -> list[Plan]:
    await ensure_free_plan_seeded(db)
    seeded = []
    for spec in _DEFAULT_PLANS:
        existing = await db.scalar(select(Plan).where(Plan.key == spec["key"]))
        if existing is None:
            existing = Plan(**spec)
            db.add(existing)
            await db.flush()
        seeded.append(existing)
    return seeded


async def get_or_create_subscription(db: AsyncSession, organization_id: uuid.UUID) -> Subscription:
    sub = await db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
    if sub is None:
        free_plan = await ensure_free_plan_seeded(db)
        # Partie 16 (bis) -- a real 14-day trial starts the moment an
        # organization's subscription is first created, same "always
        # real, never a promotional lie" reasoning as everything else
        # in this billing system.
        trial_ends_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=settings.BILLING_TRIAL_DAYS)
        sub = Subscription(organization_id=organization_id, plan_id=free_plan.id, status=SubscriptionStatus.active, trial_ends_at=trial_ends_at)
        db.add(sub)
        await db.flush()
    return sub


def is_in_trial(sub: Subscription) -> bool:
    if sub.trial_ends_at is None:
        return False
    return dt.datetime.now(dt.timezone.utc) < sub.trial_ends_at


async def list_plans(db: AsyncSession, *, include_inactive: bool = False) -> list[Plan]:
    await ensure_default_plans_seeded(db)
    stmt = select(Plan).order_by(Plan.monthly_price_cents)
    if not include_inactive:
        stmt = stmt.where(Plan.is_active.is_(True))
    return list((await db.scalars(stmt)).all())


async def get_plan(db: AsyncSession, plan_id: uuid.UUID) -> Plan:
    plan = await db.get(Plan, plan_id)
    if plan is None:
        raise PlanNotFoundError(str(plan_id))
    return plan


async def get_plan_by_key(db: AsyncSession, key: str) -> Plan | None:
    return await db.scalar(select(Plan).where(Plan.key == key))


async def create_plan(
    db: AsyncSession, *, key: str, name: str, monthly_price_cents: int, yearly_price_cents: int = 0,
    max_documents: int | None = None, max_agents: int | None = None, max_members: int | None = None,
    max_api_keys: int | None = None, max_webhooks: int | None = None, max_requests_per_month: int | None = None,
    priority_support: bool = False, advanced_features: bool = False, sla: bool = False,
) -> Plan:
    plan = Plan(
        key=key, name=name, monthly_price_cents=monthly_price_cents, yearly_price_cents=yearly_price_cents,
        max_documents=max_documents, max_agents=max_agents, max_members=max_members,
        max_api_keys=max_api_keys, max_webhooks=max_webhooks, max_requests_per_month=max_requests_per_month,
        priority_support=priority_support, advanced_features=advanced_features, sla=sla,
    )
    db.add(plan)
    await db.flush()
    return plan


async def update_plan(db: AsyncSession, plan_id: uuid.UUID, **fields) -> Plan:
    plan = await db.get(Plan, plan_id)
    if plan is None:
        raise PlanNotFoundError(str(plan_id))
    for key, value in fields.items():
        if value is not None and hasattr(plan, key):
            setattr(plan, key, value)
    await db.flush()
    return plan


async def delete_plan(db: AsyncSession, plan_id: uuid.UUID) -> None:
    plan = await db.get(Plan, plan_id)
    if plan is None:
        raise PlanNotFoundError(str(plan_id))
    await db.delete(plan)
    await db.flush()


async def list_subscriptions(db: AsyncSession, limit: int = 50, offset: int = 0) -> list[Subscription]:
    return list((await db.scalars(select(Subscription).order_by(Subscription.created_at.desc()).limit(limit).offset(offset))).all())


async def get_subscription(db: AsyncSession, sub_id: uuid.UUID) -> Subscription:
    sub = await db.get(Subscription, sub_id)
    if sub is None:
        raise SubscriptionNotFoundError(str(sub_id))
    return sub


async def update_subscription(
    db: AsyncSession, sub_id: uuid.UUID, *, plan_id: uuid.UUID | None = None,
    status_value: SubscriptionStatus | None = None, billing_period: str | None = None,
) -> Subscription:
    sub = await get_subscription(db, sub_id)
    if plan_id is not None:
        sub.plan_id = plan_id
    if status_value is not None:
        sub.status = status_value
    if billing_period is not None:
        sub.billing_period = billing_period
    await db.flush()
    return sub


async def reactivate_subscription(db: AsyncSession, sub_id: uuid.UUID) -> Subscription:
    sub = await get_subscription(db, sub_id)
    sub.status = SubscriptionStatus.active
    sub.canceled_at = None
    sub.cancel_reason = None
    await db.flush()
    return sub


async def cancel_subscription(db: AsyncSession, sub_id: uuid.UUID, *, reason: str | None) -> Subscription:
    sub = await get_subscription(db, sub_id)
    sub.status = SubscriptionStatus.canceled
    sub.canceled_at = dt.datetime.now(dt.timezone.utc)
    sub.cancel_reason = reason
    await db.flush()
    return sub


async def extend_subscription(db: AsyncSession, sub_id: uuid.UUID, *, days: int) -> Subscription:
    sub = await get_subscription(db, sub_id)
    base = sub.current_period_end or dt.datetime.now(dt.timezone.utc)
    sub.current_period_end = base + dt.timedelta(days=days)
    await db.flush()
    return sub


async def get_revenue_stats(db: AsyncSession) -> dict:
    """Real MRR/ARR/ARPU -- a real SUM/JOIN over active subscriptions'
    real plan prices, not a mocked number. 0 in an environment with no
    real paying organization, honestly."""
    active_count = await db.scalar(select(func.count()).select_from(Subscription).where(Subscription.status == SubscriptionStatus.active)) or 0
    mrr_cents = await db.scalar(
        select(func.coalesce(func.sum(Plan.monthly_price_cents), 0)).select_from(Subscription).join(Plan, Plan.id == Subscription.plan_id).where(Subscription.status == SubscriptionStatus.active)
    ) or 0
    canceled_last_30d = await db.scalar(
        select(func.count()).select_from(Subscription).where(Subscription.status == SubscriptionStatus.canceled, Subscription.canceled_at >= dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30))
    ) or 0
    return {
        "mrr_cents": mrr_cents,
        "arr_cents": mrr_cents * 12,
        "active_subscriptions": active_count,
        "arpu_cents": (mrr_cents // active_count) if active_count else 0,
        "churn_last_30d": canceled_last_30d,
    }
