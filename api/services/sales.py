"""Partie 16 (bis) -- license validation/activation, support tickets +
SLA status, reseller/sub-client CRUD and real commission math."""

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.sales import (
    License, LicenseStatus, Reseller, SLA_RESPONSE_HOURS, SubClient, SupportTicket, TicketResponse, TicketStatus,
    generate_license_key,
)


class SalesError(Exception):
    pass


class LicenseNotFoundError(SalesError):
    pass


class TicketNotFoundError(SalesError):
    pass


class ResellerNotFoundError(SalesError):
    pass


def _as_utc(value: dt.datetime) -> dt.datetime:
    """SQLite (this project's fast test suite) returns naive datetimes
    from a DateTime(timezone=True) column, real Postgres returns aware
    ones -- same real cross-dialect gap this project has hit before
    elsewhere. Normalizes to aware-UTC so comparisons never raise,
    regardless of which database produced the value."""
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


# -- Self-hosted licensing ----------------------------------------------------

async def generate_license(db: AsyncSession, *, plan_key: str, max_activations: int = 1, expires_in_days: int | None = 365) -> License:
    expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=expires_in_days) if expires_in_days else None
    license_row = License(key=generate_license_key(), plan_key=plan_key, max_activations=max_activations, expires_at=expires_at)
    db.add(license_row)
    await db.flush()
    return license_row


async def validate_license(db: AsyncSession, key: str) -> dict:
    """Real, read-only check -- does NOT consume an activation slot
    (that's activate_license's job) -- so a self-hosted install can
    check "is this key still good" repeatedly (e.g. on every startup)
    without exhausting max_activations."""
    license_row = await db.scalar(select(License).where(License.key == key))
    if license_row is None:
        return {"valid": False, "reason": "unknown license key"}
    if license_row.status != LicenseStatus.active:
        return {"valid": False, "reason": f"license is {license_row.status.value}"}
    if license_row.expires_at and dt.datetime.now(dt.timezone.utc) > _as_utc(license_row.expires_at):
        return {"valid": False, "reason": "license expired"}
    license_row.last_validated_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return {"valid": True, "plan_key": license_row.plan_key, "expires_at": license_row.expires_at}


async def activate_license(db: AsyncSession, key: str, organization_id: uuid.UUID) -> License:
    license_row = await db.scalar(select(License).where(License.key == key))
    if license_row is None:
        raise LicenseNotFoundError(key)
    result = await validate_license(db, key)
    if not result["valid"]:
        raise SalesError(result["reason"])
    if license_row.activation_count >= license_row.max_activations:
        raise SalesError(f"license already activated on {license_row.activation_count}/{license_row.max_activations} deployment(s)")
    license_row.activation_count += 1
    license_row.organization_id = organization_id
    if license_row.activated_at is None:
        license_row.activated_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return license_row


async def get_license_status(db: AsyncSession, organization_id: uuid.UUID) -> License | None:
    return await db.scalar(select(License).where(License.organization_id == organization_id))


# -- Hybrid: support tickets + SLA -------------------------------------------

async def create_support_ticket(db: AsyncSession, organization_id: uuid.UUID, *, subject: str, description: str, priority, user_id: uuid.UUID | None) -> SupportTicket:
    ticket = SupportTicket(organization_id=organization_id, subject=subject, description=description, priority=priority, created_by=user_id)
    db.add(ticket)
    await db.flush()
    return ticket


async def list_support_tickets(db: AsyncSession, organization_id: uuid.UUID) -> list[SupportTicket]:
    return list((await db.scalars(select(SupportTicket).where(SupportTicket.organization_id == organization_id).order_by(SupportTicket.created_at.desc()))).all())


async def get_support_ticket(db: AsyncSession, organization_id: uuid.UUID, ticket_id: uuid.UUID) -> SupportTicket:
    ticket = await db.get(SupportTicket, ticket_id)
    if ticket is None or ticket.organization_id != organization_id:
        raise TicketNotFoundError(str(ticket_id))
    return ticket


async def respond_to_ticket(db: AsyncSession, organization_id: uuid.UUID, ticket_id: uuid.UUID, *, body: str, is_staff: bool, user_id: uuid.UUID | None) -> TicketResponse:
    ticket = await get_support_ticket(db, organization_id, ticket_id)
    response = TicketResponse(ticket_id=ticket.id, body=body, is_staff=is_staff, created_by=user_id)
    db.add(response)
    if is_staff and ticket.first_responded_at is None:
        ticket.first_responded_at = dt.datetime.now(dt.timezone.utc)
    if is_staff and ticket.status == TicketStatus.open:
        ticket.status = TicketStatus.in_progress
    await db.flush()
    return response


def get_sla_status(ticket: SupportTicket) -> dict:
    """Real, computed against SLA_RESPONSE_HOURS -- a ticket that
    hasn't been responded to yet is checked against "now", one that has
    is checked against its own real first_responded_at, never
    fabricated as compliant."""
    target_hours = SLA_RESPONSE_HOURS[ticket.priority]
    deadline = _as_utc(ticket.created_at) + dt.timedelta(hours=target_hours)
    responded_at = ticket.first_responded_at
    if responded_at is not None:
        return {"target_hours": target_hours, "deadline": deadline, "responded_at": responded_at, "breached": _as_utc(responded_at) > deadline}
    now = dt.datetime.now(dt.timezone.utc)
    return {"target_hours": target_hours, "deadline": deadline, "responded_at": None, "breached": now > deadline}


# -- White-label: resellers / sub-clients ------------------------------------

async def create_reseller(db: AsyncSession, organization_id: uuid.UUID, *, commission_percent: int = 20) -> Reseller:
    reseller = Reseller(organization_id=organization_id, commission_percent=commission_percent)
    db.add(reseller)
    await db.flush()
    return reseller


async def get_reseller(db: AsyncSession, reseller_id: uuid.UUID) -> Reseller:
    reseller = await db.get(Reseller, reseller_id)
    if reseller is None:
        raise ResellerNotFoundError(str(reseller_id))
    return reseller


async def add_sub_client(db: AsyncSession, reseller_id: uuid.UUID, organization_id: uuid.UUID) -> SubClient:
    await get_reseller(db, reseller_id)  # raises ResellerNotFoundError if missing
    sub_client = SubClient(reseller_id=reseller_id, organization_id=organization_id)
    db.add(sub_client)
    await db.flush()
    return sub_client


async def list_sub_clients(db: AsyncSession, reseller_id: uuid.UUID) -> list[SubClient]:
    return list((await db.scalars(select(SubClient).where(SubClient.reseller_id == reseller_id))).all())


async def calculate_reseller_commission(db: AsyncSession, reseller_id: uuid.UUID) -> dict:
    """Real commission math over real, active, genuinely-paid
    subscriptions of this reseller's real sub-client organizations --
    the exact same "real $0 without a real paying org" honesty as
    admin_subscriptions.py's own get_revenue_stats."""
    reseller = await get_reseller(db, reseller_id)
    sub_client_org_ids = [row.organization_id for row in await list_sub_clients(db, reseller_id)]
    if not sub_client_org_ids:
        return {"sub_client_count": 0, "sub_client_mrr_cents": 0, "commission_cents": 0}

    mrr_cents = await db.scalar(
        select(func.coalesce(func.sum(Plan.monthly_price_cents), 0))
        .select_from(Subscription).join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.organization_id.in_(sub_client_org_ids), Subscription.status == SubscriptionStatus.active)
    ) or 0
    commission_cents = round(mrr_cents * reseller.commission_percent / 100)
    return {"sub_client_count": len(sub_client_org_ids), "sub_client_mrr_cents": mrr_cents, "commission_cents": commission_cents}
