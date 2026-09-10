"""Partie 11.2 -- platform-admin organization management. Reuses the
existing, real Organization/OrganizationMember/quota/usage machinery
rather than duplicating it (member listing, usage figures)."""

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.agent import Agent
from api.models.document import Document
from api.models.organization import Organization, OrganizationMember


class OrganizationAdminError(Exception):
    pass


class OrganizationNotFoundError(OrganizationAdminError):
    pass


async def list_organizations_admin(db: AsyncSession, *, limit: int = 20, offset: int = 0, suspended: bool | None = None) -> tuple[list[Organization], int]:
    filters = [Organization.is_suspended == suspended] if suspended is not None else []
    total = await db.scalar(select(func.count()).select_from(Organization).where(*filters)) or 0
    rows = list((await db.scalars(
        select(Organization).where(*filters).order_by(Organization.created_at.desc()).limit(limit).offset(offset)
    )).all())
    return rows, total


async def get_organization_admin(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    org = await db.get(Organization, org_id)
    if org is None:
        raise OrganizationNotFoundError(str(org_id))
    return org


async def update_organization_admin(db: AsyncSession, org_id: uuid.UUID, *, name: str | None = None) -> Organization:
    org = await get_organization_admin(db, org_id)
    if name is not None:
        org.name = name
    await db.flush()
    return org


async def delete_organization_admin(db: AsyncSession, org_id: uuid.UUID) -> None:
    org = await get_organization_admin(db, org_id)
    await db.delete(org)
    await db.flush()


async def suspend_organization(db: AsyncSession, org_id: uuid.UUID, *, reason: str | None) -> Organization:
    org = await get_organization_admin(db, org_id)
    org.is_suspended = True
    org.suspended_at = dt.datetime.now(dt.timezone.utc)
    org.suspended_reason = reason
    await db.flush()
    return org


async def activate_organization(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    org = await get_organization_admin(db, org_id)
    org.is_suspended = False
    org.suspended_at = None
    org.suspended_reason = None
    await db.flush()
    return org


async def get_organization_members_admin(db: AsyncSession, org_id: uuid.UUID) -> list[OrganizationMember]:
    return list((await db.scalars(
        select(OrganizationMember).options(selectinload(OrganizationMember.user)).where(OrganizationMember.organization_id == org_id)
    )).all())


async def get_organization_usage_admin(db: AsyncSession, org_id: uuid.UUID) -> dict:
    documents = await db.scalar(select(func.count()).select_from(Document).where(Document.organization_id == org_id)) or 0
    agents = await db.scalar(select(func.count()).select_from(Agent).where(Agent.organization_id == org_id)) or 0
    members = await db.scalar(select(func.count()).select_from(OrganizationMember).where(OrganizationMember.organization_id == org_id)) or 0
    return {"documents": documents, "agents": agents, "members": members}
