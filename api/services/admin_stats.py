"""
Partie 11.1 -- real global platform statistics, aggregated from the
same tables every other real feature in this codebase already writes
to (User, Organization, Document, Agent, Conversation,
OrganizationAPIKey). No fabricated numbers: `revenue`/`mrr`/`arr` come
from api/services/admin_subscriptions.py's real Plan/Subscription
tables and are 0 in an environment with no paying organization, not a
placeholder pretending otherwise.
"""

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.agent import Agent
from api.models.conversation import Conversation
from api.models.document import Document
from api.models.organization import Organization
from api.models.organization_api_key import OrganizationAPIKey
from api.models.user import User


async def _count(db: AsyncSession, model, *filters) -> int:
    return await db.scalar(select(func.count()).select_from(model).where(*filters)) or 0


async def get_global_stats(db: AsyncSession) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    last_30d = now - dt.timedelta(days=30)

    total_users = await _count(db, User)
    active_users = await _count(db, User, User.is_active.is_(True))
    new_users_30d = await _count(db, User, User.created_at >= last_30d)

    total_orgs = await _count(db, Organization)
    active_orgs = await _count(db, Organization, Organization.is_suspended.is_(False))
    new_orgs_30d = await _count(db, Organization, Organization.created_at >= last_30d)

    total_documents = await _count(db, Document)
    total_agents = await _count(db, Agent)
    active_agents = await _count(db, Agent, Agent.status == "active")
    total_conversations = await _count(db, Conversation)

    total_api_requests = await db.scalar(select(func.coalesce(func.sum(OrganizationAPIKey.quota_used), 0))) or 0

    from api.services.admin_subscriptions import get_revenue_stats

    revenue = await get_revenue_stats(db)

    return {
        "users": {"total": total_users, "active": active_users, "new_last_30d": new_users_30d},
        "organizations": {"total": total_orgs, "active": active_orgs, "new_last_30d": new_orgs_30d},
        "documents": {"total": total_documents},
        "agents": {"total": total_agents, "active": active_agents},
        "conversations": {"total": total_conversations},
        "api_usage": {"total_requests": total_api_requests},
        "revenue": revenue,
        "generated_at": now,
    }


async def get_user_stats(db: AsyncSession, days: int = 30) -> dict:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rows = (await db.execute(
        select(func.date(User.created_at), func.count()).where(User.created_at >= since).group_by(func.date(User.created_at)).order_by(func.date(User.created_at))
    )).all()
    return {
        "total": await _count(db, User),
        "active": await _count(db, User, User.is_active.is_(True)),
        "verified": await _count(db, User, User.is_email_verified.is_(True)),
        "growth_by_day": [{"date": str(d), "count": c} for d, c in rows],
    }


async def get_organization_stats(db: AsyncSession, days: int = 30) -> dict:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rows = (await db.execute(
        select(func.date(Organization.created_at), func.count()).where(Organization.created_at >= since).group_by(func.date(Organization.created_at)).order_by(func.date(Organization.created_at))
    )).all()
    return {
        "total": await _count(db, Organization),
        "active": await _count(db, Organization, Organization.is_suspended.is_(False)),
        "suspended": await _count(db, Organization, Organization.is_suspended.is_(True)),
        "growth_by_day": [{"date": str(d), "count": c} for d, c in rows],
    }


async def get_api_usage_stats(db: AsyncSession) -> dict:
    total_keys = await _count(db, OrganizationAPIKey, OrganizationAPIKey.is_active.is_(True))
    total_requests = await db.scalar(select(func.coalesce(func.sum(OrganizationAPIKey.quota_used), 0))) or 0
    return {"active_keys": total_keys, "total_requests": total_requests}


async def get_conversation_stats(db: AsyncSession) -> dict:
    return {"total": await _count(db, Conversation)}


async def get_document_stats(db: AsyncSession) -> dict:
    total_bytes = await db.scalar(select(func.coalesce(func.sum(Document.file_size), 0))) or 0
    return {"total": await _count(db, Document), "total_bytes": total_bytes}
