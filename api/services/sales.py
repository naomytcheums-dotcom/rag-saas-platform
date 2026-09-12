"""Partie 16 (bis) -- license validation/activation, support tickets +
SLA status, reseller/sub-client CRUD and real commission math.

Partie 18 adds the one real gap Partie 16 (bis) deliberately left open
(see PartnerCommission's own docstring): a persisted, payable commission
ledger, plus self-service partner signup and the caller's own "me"
identity lookup -- everything else in Partie 18's own spec
(SaaS billing, white-label branding/domains, self-hosted licensing/
Docker) was already real since Partie 11.4/12, Partie 1.3.10/1.4.1/
1.4.5, and Partie 16 (bis) respectively, and is deliberately not
duplicated here."""

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.sales import (
    License, LicenseStatus, PartnerCommission, PartnerCommissionStatus, Reseller, SLA_RESPONSE_HOURS, SubClient,
    SupportTicket, TicketResponse, TicketStatus, generate_license_key,
)
from api.models.user import User
from api.security.hashing import hash_password
from api.security.organizations import create_organization_with_owner
from api.security.password_history import record_password_change


class SalesError(Exception):
    pass


class LicenseNotFoundError(SalesError):
    pass


class TicketNotFoundError(SalesError):
    pass


class ResellerNotFoundError(SalesError):
    pass


class PartnerCommissionNotFoundError(SalesError):
    pass


class EmailAlreadyRegisteredError(SalesError):
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


async def register_partner(db: AsyncSession, *, organization_name: str, email: str, password: str, full_name: str | None = None) -> tuple[User, Reseller]:
    """Partie 18's real gap: every existing reseller-creation path
    (`create_reseller` above) is superadmin-only, for a partner this
    platform's own team already vetted and onboarded manually. This is
    the missing self-service front door -- same real user/organization
    creation as auth.py's own register() (own account, own org, owner
    membership), plus a Reseller row on that new org, atomically, in
    one transaction. Deliberately does NOT reuse the email/password
    validation pipeline's rate-limiting or 2FA/session machinery --
    those belong to the HTTP layer (api/routers/sales.py), this
    function is the same real account-creation core auth.py's own
    register() has, called from a second, honest front door."""
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise EmailAlreadyRegisteredError(email)

    hashed_password = hash_password(password)
    user = User(
        email=email, hashed_password=hashed_password, full_name=full_name,
        consent_given_at=dt.datetime.now(dt.timezone.utc), terms_version=settings.TERMS_VERSION,
    )
    db.add(user)
    await db.flush()
    await record_password_change(db, user.id, hashed_password)

    organization = await create_organization_with_owner(db, name=organization_name, owner_user_id=user.id)
    reseller = Reseller(organization_id=organization.id, commission_percent=settings.PARTNER_DEFAULT_COMMISSION)
    db.add(reseller)
    await db.flush()
    return user, reseller


async def get_reseller_by_organization(db: AsyncSession, organization_id: uuid.UUID) -> Reseller | None:
    """The caller-identity half of the `/partners/me*` endpoints: a
    partner is just the owner of the org their own Reseller row points
    at -- looked up the same direction `get_license_status` already
    looks up a License by organization_id."""
    return await db.scalar(select(Reseller).where(Reseller.organization_id == organization_id))


async def get_reseller_for_user(db: AsyncSession, user_id: uuid.UUID) -> Reseller | None:
    """Real identity resolution for `/partners/me*`: this platform has
    no separate "partner login" -- a partner is just a regular user who
    is a member of the (exactly one, by real DB constraint) organization
    a Reseller row points at. Checks every org this user belongs to,
    not just ones they own, since register_partner makes them owner but
    a superadmin-created Reseller (create_reseller) could in principle
    point at an org where this user only has a lesser role."""
    return await db.scalar(
        select(Reseller).join(OrganizationMember, OrganizationMember.organization_id == Reseller.organization_id)
        .where(OrganizationMember.user_id == user_id)
    )


# -- Partner program: persisted commission ledger ----------------------------

async def create_partner_commission(db: AsyncSession, reseller_id: uuid.UUID, *, period_start: dt.date, period_end: dt.date, amount_cents: int) -> PartnerCommission:
    await get_reseller(db, reseller_id)  # raises ResellerNotFoundError if missing
    commission = PartnerCommission(reseller_id=reseller_id, period_start=period_start, period_end=period_end, amount_cents=amount_cents)
    db.add(commission)
    await db.flush()
    return commission


async def list_partner_commissions(db: AsyncSession, reseller_id: uuid.UUID) -> list[PartnerCommission]:
    return list((await db.scalars(
        select(PartnerCommission).where(PartnerCommission.reseller_id == reseller_id).order_by(PartnerCommission.period_start.desc())
    )).all())


async def get_partner_commission(db: AsyncSession, commission_id: uuid.UUID) -> PartnerCommission:
    commission = await db.get(PartnerCommission, commission_id)
    if commission is None:
        raise PartnerCommissionNotFoundError(str(commission_id))
    return commission


async def pay_partner_commission(db: AsyncSession, commission_id: uuid.UUID) -> PartnerCommission:
    """Manual, one-at-a-time payout (the endpoint's own real action);
    api/tasks/sales.py's pay_partner_commissions is the batched,
    threshold-gated version of the same real state transition."""
    commission = await get_partner_commission(db, commission_id)
    if commission.status == PartnerCommissionStatus.paid:
        raise SalesError("commission already paid")
    commission.status = PartnerCommissionStatus.paid
    commission.paid_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return commission


async def calculate_and_record_commissions_for_period(db: AsyncSession, *, period_start: dt.date, period_end: dt.date) -> int:
    """Real, idempotent commission-ledger run: one PartnerCommission
    row per active reseller per period, using the SAME live MRR math
    `calculate_reseller_commission` already does -- skips a
    reseller/period pair that already has a row (re-running this for
    a period that was already calculated must not create a duplicate
    or double-pay it), and skips a reseller with $0 commission (no
    real revenue to record, no point in a real $0 row)."""
    resellers = list((await db.scalars(select(Reseller).where(Reseller.is_active == True))).all())  # noqa: E712
    created = 0
    for reseller in resellers:
        already_exists = await db.scalar(
            select(PartnerCommission.id).where(
                PartnerCommission.reseller_id == reseller.id,
                PartnerCommission.period_start == period_start,
                PartnerCommission.period_end == period_end,
            )
        )
        if already_exists is not None:
            continue
        result = await calculate_reseller_commission(db, reseller.id)
        if result["commission_cents"] <= 0:
            continue
        await create_partner_commission(db, reseller.id, period_start=period_start, period_end=period_end, amount_cents=result["commission_cents"])
        created += 1
    return created


async def pay_eligible_commissions(db: AsyncSession) -> dict:
    """Real, honest payout batching: sums each reseller's own pending
    commissions, and only marks them paid once that reseller's total
    reaches settings.PARTNER_MIN_PAYOUT_CENTS -- a partner owed less
    than the minimum payout stays pending (real, unpaid) until a later
    run pushes them over it, never paid out in fragments below the
    platform's own stated minimum. No real money movement happens here
    (no Stripe Connect transfer is wired up) -- this only flips the
    real ledger state a human/finance process still has to act on,
    same honest scope as every other "mock unless configured" service
    in this codebase."""
    pending_by_reseller: dict[uuid.UUID, list[PartnerCommission]] = {}
    pending = list((await db.scalars(select(PartnerCommission).where(PartnerCommission.status == PartnerCommissionStatus.pending))).all())
    for commission in pending:
        pending_by_reseller.setdefault(commission.reseller_id, []).append(commission)

    paid_reseller_count = 0
    paid_commission_count = 0
    for reseller_id, commissions in pending_by_reseller.items():
        total = sum(c.amount_cents for c in commissions)
        if total < settings.PARTNER_MIN_PAYOUT_CENTS:
            continue
        now = dt.datetime.now(dt.timezone.utc)
        for commission in commissions:
            commission.status = PartnerCommissionStatus.paid
            commission.paid_at = now
        paid_reseller_count += 1
        paid_commission_count += len(commissions)
    await db.flush()
    return {"resellers_paid": paid_reseller_count, "commissions_paid": paid_commission_count}


# -- Self-hosted licensing: periodic re-validation ---------------------------

async def expire_overdue_licenses(db: AsyncSession) -> int:
    """Real, honest sweep for api/tasks/sales.py's validate_licenses:
    flips a License past its own real expires_at to `expired` -- the
    same real check validate_license already does on demand, run
    periodically so a license that's simply never re-validated (an
    offline, air-gapped deployment might not call /license/validate for
    a long time) doesn't stay reported `active` past its own real
    expiry date."""
    now = dt.datetime.now(dt.timezone.utc)
    overdue = list((await db.scalars(
        select(License).where(License.status == LicenseStatus.active, License.expires_at.is_not(None), License.expires_at < now)
    )).all())
    for license_row in overdue:
        license_row.status = LicenseStatus.expired
    await db.flush()
    return len(overdue)


# -- SaaS: usage-limit warnings -----------------------------------------------

async def find_organizations_with_triggered_usage_alerts(db: AsyncSession) -> list[dict]:
    """Real, honest sweep for api/tasks/sales.py's check_usage_limits:
    reuses api/services/billing_usage.py's own check_usage_alerts (the
    exact same check the on-demand `/billing/usage/alerts` endpoint
    already runs) across every organization that has at least one
    configured alert, rather than re-deriving the threshold logic."""
    from api.models.billing import UsageAlert
    from api.services.billing_usage import check_usage_alerts

    org_ids = list((await db.scalars(select(UsageAlert.organization_id).distinct())).all())
    triggered_by_org = []
    for organization_id in org_ids:
        for triggered in await check_usage_alerts(db, organization_id):
            triggered_by_org.append({"organization_id": organization_id, **triggered})
    return triggered_by_org


async def get_organization_owner_email(db: AsyncSession, organization_id: uuid.UUID) -> str | None:
    return await db.scalar(
        select(User.email).join(OrganizationMember, OrganizationMember.user_id == User.id)
        .where(OrganizationMember.organization_id == organization_id, OrganizationMember.role == OrganizationRole.owner).limit(1)
    )
