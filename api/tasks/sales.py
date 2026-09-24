"""Partie 18 -- Celery jobs for the sales models: partner commission
calculation/payout, self-hosted license re-validation, and SaaS
usage-limit warnings. Same sync-engine pattern as api/tasks/billing.py
-- Celery's worker model is sync by default, so these re-implement
(not import) the async logic in api/services/sales.py, same precedent
as billing.py's own tasks vs api/services/billing_usage.py."""

import datetime as dt
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.billing import UsageAlert
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.sales import License, LicenseStatus, PartnerCommission, PartnerCommissionStatus, Reseller, SubClient
from api.models.user import User
from api.tasks.celery_app import celery_app
from api.tasks._sync_engine import sync_engine as _sync_engine

logger = logging.getLogger(__name__)



@celery_app.task(name="api.tasks.sales.calculate_partner_commissions")
def calculate_partner_commissions() -> int:
    """Monthly commission-ledger run, for the month just elapsed --
    same real MRR math as api/services/sales.py's own
    calculate_reseller_commission, one persisted row per active
    reseller per period, skipped if that period's row already exists
    (idempotent against a re-run) or the real commission is $0."""
    today = dt.date.today()
    period_end = today.replace(day=1) - dt.timedelta(days=1)
    period_start = period_end.replace(day=1)
    created = 0

    with SyncSession(_sync_engine) as db:
        resellers = db.scalars(select(Reseller).where(Reseller.is_active == True)).all()  # noqa: E712
        for reseller in resellers:
            already_exists = db.scalar(
                select(PartnerCommission.id).where(
                    PartnerCommission.reseller_id == reseller.id,
                    PartnerCommission.period_start == period_start,
                    PartnerCommission.period_end == period_end,
                )
            )
            if already_exists is not None:
                continue
            sub_client_org_ids = [row.organization_id for row in db.scalars(select(SubClient).where(SubClient.reseller_id == reseller.id)).all()]
            if not sub_client_org_ids:
                continue
            mrr_cents = db.scalar(
                select(Plan.monthly_price_cents).select_from(Subscription).join(Plan, Plan.id == Subscription.plan_id)
                .where(Subscription.organization_id.in_(sub_client_org_ids), Subscription.status == SubscriptionStatus.active)
            ) or 0
            commission_cents = round(mrr_cents * reseller.commission_percent / 100)
            if commission_cents <= 0:
                continue
            db.add(PartnerCommission(reseller_id=reseller.id, period_start=period_start, period_end=period_end, amount_cents=commission_cents))
            created += 1
        db.commit()

    logger.info("calculate_partner_commissions: %d commission row(s) created for %s..%s", created, period_start, period_end)
    return created


@celery_app.task(name="api.tasks.sales.pay_partner_commissions")
def pay_partner_commissions() -> int:
    """Real, honest payout batching -- marks a reseller's pending
    commissions paid only once their total reaches
    settings.PARTNER_MIN_PAYOUT_CENTS. No real money movement (no
    Stripe Connect transfer wired up): this flips the real ledger
    state a finance process still has to act on, the same honest scope
    as auto_refill_credits above."""
    paid_reseller_count = 0

    with SyncSession(_sync_engine) as db:
        pending = db.scalars(select(PartnerCommission).where(PartnerCommission.status == PartnerCommissionStatus.pending)).all()
        by_reseller: dict = {}
        for commission in pending:
            by_reseller.setdefault(commission.reseller_id, []).append(commission)

        now = dt.datetime.now(dt.timezone.utc)
        for reseller_id, commissions in by_reseller.items():
            total = sum(c.amount_cents for c in commissions)
            if total < settings.PARTNER_MIN_PAYOUT_CENTS:
                continue
            for commission in commissions:
                commission.status = PartnerCommissionStatus.paid
                commission.paid_at = now
            paid_reseller_count += 1
        db.commit()

    logger.info("pay_partner_commissions: %d reseller(s) paid out", paid_reseller_count)
    return paid_reseller_count


@celery_app.task(name="api.tasks.sales.validate_licenses")
def validate_licenses() -> int:
    """Real, periodic re-validation sweep: a License that's never
    explicitly re-checked (an offline, air-gapped self-hosted
    deployment might not call /license/validate for a long time) still
    gets flipped to `expired` once its own real expires_at has passed,
    rather than staying reported `active` past its real expiry."""
    now = dt.datetime.now(dt.timezone.utc)
    expired_count = 0

    with SyncSession(_sync_engine) as db:
        overdue = db.scalars(
            select(License).where(License.status == LicenseStatus.active, License.expires_at.is_not(None), License.expires_at < now)
        ).all()
        for license_row in overdue:
            license_row.status = LicenseStatus.expired
            expired_count += 1
        db.commit()

    logger.info("validate_licenses: %d license(s) expired", expired_count)
    return expired_count


@celery_app.task(name="api.tasks.sales.check_usage_limits")
def check_usage_limits() -> int:
    """Real, periodic warning sweep -- the same real, direct resource
    COUNT api/services/billing_usage.py's check_plan_resource_limit
    already does on demand (documents/agents/members counted directly
    against the real Plan.max_* column, not a separate usage ledger),
    across every organization that has at least one configured alert,
    emailing the org owner when a real count crosses that alert's own
    threshold. The real hard block already happens at request time
    (billing_usage.check_limits); this is only the heads-up before that
    point is reached."""
    from api.models.agent import Agent
    from api.models.document import Document
    from api.services.email_branding import send_branded_usage_limit_warning_email_sync

    _COUNT_QUERY = {
        "documents": lambda org_id: select(func.count()).select_from(Document).where(Document.organization_id == org_id),
        "agents": lambda org_id: select(func.count()).select_from(Agent).where(Agent.organization_id == org_id),
        "members": lambda org_id: select(func.count()).select_from(OrganizationMember).where(OrganizationMember.organization_id == org_id),
    }
    _LIMIT_ATTR = {"documents": "max_documents", "agents": "max_agents", "members": "max_members"}
    sent = 0

    with SyncSession(_sync_engine) as db:
        org_ids = db.scalars(select(UsageAlert.organization_id).distinct()).all()
        for organization_id in org_ids:
            alerts = db.scalars(select(UsageAlert).where(UsageAlert.organization_id == organization_id)).all()
            if not alerts:
                continue
            sub = db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
            plan = db.get(Plan, sub.plan_id) if sub else None
            if plan is None:
                continue
            owner_email = db.scalar(
                select(User.email).join(OrganizationMember, OrganizationMember.user_id == User.id)
                .where(OrganizationMember.organization_id == organization_id, OrganizationMember.role == OrganizationRole.owner).limit(1)
            )
            if not owner_email:
                continue
            for alert in alerts:
                limit = getattr(plan, _LIMIT_ATTR.get(alert.resource_type, ""), None)
                count_query = _COUNT_QUERY.get(alert.resource_type)
                if not limit or count_query is None:
                    continue
                used = db.scalar(count_query(organization_id)) or 0
                percent = round((used / limit) * 100)
                if percent < alert.threshold_percent:
                    continue
                try:
                    send_branded_usage_limit_warning_email_sync(db, organization_id, owner_email, alert.resource_type, percent, limit)
                    sent += 1
                except Exception:
                    logger.warning("check_usage_limits: email delivery failed for org %s", organization_id, exc_info=True)

    logger.info("check_usage_limits: %d warning(s) sent", sent)
    return sent
