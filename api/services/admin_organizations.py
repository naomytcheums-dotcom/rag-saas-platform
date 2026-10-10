"""Partie 11.2 -- platform-admin organization management. Reuses the
existing, real Organization/OrganizationMember/quota/usage machinery
rather than duplicating it (member listing, usage figures)."""

import datetime as dt
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.agent import Agent
from api.models.document import Document
from api.models.organization import Organization, OrganizationMember

logger = logging.getLogger(__name__)


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


async def delete_organization_admin(db: AsyncSession, org_id: uuid.UUID) -> list[str]:
    """Deletes the organization and returns the object-storage keys of its files, to be purged once the deletion is committed.
    A provider subscription (Stripe) is cancelled first so that the customer is not billed for an organization that no longer exists."""
    from api.models.admin import Subscription
    from api.models.media import MediaAsset, MediaFrame

    org = await get_organization_admin(db, org_id)
    sub = await db.scalar(select(Subscription).where(Subscription.organization_id == org_id))
    if sub is not None and sub.stripe_subscription_id:
        from api.services import billing_stripe

        try:
            await billing_stripe.cancel_stripe_subscription(db, org_id, at_period_end=False)
        except Exception as exc:  # noqa: BLE001 -- the deletion must not hang on the provider; the failure is logged for follow-up
            logger.error("organization %s deleted but its Stripe subscription could not be cancelled (%s)", org_id, type(exc).__name__)
    keys = list((await db.scalars(select(Document.file_key).where(Document.organization_id == org_id, Document.file_key.is_not(None)))).all())
    keys += list((await db.scalars(select(MediaAsset.file_key).where(MediaAsset.organization_id == org_id, MediaAsset.file_key != ""))).all())
    keys += list((await db.scalars(
        select(MediaFrame.file_key).join(MediaAsset, MediaAsset.id == MediaFrame.media_asset_id).where(MediaAsset.organization_id == org_id)
    )).all())
    await db.delete(org)
    await db.flush()
    return [key for key in keys if key]


def purge_organization_storage(keys: list[str]) -> None:
    """Best effort, after the commit (`delete_document_file` never raises): objects of a deleted organization are not left orphaned."""
    from api.services.document_storage import delete_document_file

    for key in keys:
        delete_document_file(key)


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
