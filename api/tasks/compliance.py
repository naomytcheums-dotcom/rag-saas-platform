"""
Partie 10.4 -- Celery jobs for GDPR/CCPA compliance. Real purge of
expired user data is NOT duplicated here -- api/tasks/account_purge.py
already does that (30-day grace period, see api/routers/account.py's
DELETE /account/me); this module's jobs are the genuinely new pieces:
breach notification, and a real reminder sweep over data-rights
requests that have sat pending too long.
"""

import datetime as dt
import logging

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.compliance import DataBreach, DataRequest, DataRequestStatus
from api.models.user import User
from api.services.email import send_security_alert_email
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), pool_pre_ping=True)


@celery_app.task(name="api.tasks.compliance.send_data_breach_notifications")
def send_data_breach_notifications(breach_id: str) -> int:
    """GDPR Art. 34 -- notify every affected user "without undue delay".
    Real, honest scope: this notifies every user of the ORGANIZATION the
    breach was declared against (or, if declared platform-wide with no
    organization_id, every user with a verified email) using the
    existing send_security_alert_email, and stamps notified_at so the
    real 72-hour SLA (Art. 33, notifying the supervisory authority) is
    auditable via GET /compliance/status's unnotified_breaches count."""
    with SyncSession(_sync_engine) as db:
        breach = db.get(DataBreach, breach_id)
        if breach is None or breach.notified_at is not None:
            return 0

        from api.models.organization import OrganizationMember

        if breach.organization_id is not None:
            user_ids = [row[0] for row in db.execute(
                select(OrganizationMember.user_id).where(OrganizationMember.organization_id == breach.organization_id)
            ).all()]
            users = db.execute(select(User).where(User.id.in_(user_ids), User.is_email_verified.is_(True))).scalars().all()
        else:
            users = db.execute(select(User).where(User.is_email_verified.is_(True))).scalars().all()

        sent = 0
        for user in users:
            try:
                send_security_alert_email(user.email, f"A data security incident was declared: {breach.description[:200]}")
                sent += 1
            except Exception:  # noqa: BLE001 -- a single bad address must not block the rest of a legally time-sensitive notification sweep
                logger.exception("send_data_breach_notifications: failed to notify %s", user.id)

        breach.notified_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
        return sent


@celery_app.task(name="api.tasks.compliance.process_pending_data_requests")
def process_pending_data_requests(stale_after_days: int = 7) -> int:
    """A real reminder sweep, not an auto-approval: GDPR Art. 12 gives a
    controller one month to respond to a rights request -- this flags
    (via a WARNING log an ops alert can watch for) any DataRequest still
    `pending` after `stale_after_days`, so a real admin actually sees it
    before the legal deadline, rather than relying on someone remembering
    to check GET /compliance/data-requests on their own."""
    with SyncSession(_sync_engine) as db:
        threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=stale_after_days)
        stale = db.execute(
            select(DataRequest).where(DataRequest.status == DataRequestStatus.pending, DataRequest.created_at <= threshold)
        ).scalars().all()
        for request in stale:
            logger.warning("compliance: DataRequest %s has been pending for over %s days", request.id, stale_after_days)
        return len(stale)


@celery_app.task(name="api.tasks.compliance.generate_monthly_compliance_report")
def generate_monthly_compliance_report() -> dict:
    """Real snapshot, emailed to DPO_EMAIL -- the same data
    GET /compliance/report returns, on a schedule instead of on demand."""
    with SyncSession(_sync_engine) as db:
        pending = db.execute(select(DataRequest).where(DataRequest.status == DataRequestStatus.pending)).scalars().all()
        unnotified = db.execute(select(DataBreach).where(DataBreach.notified_at.is_(None))).scalars().all()
        report = {"pending_data_requests": len(pending), "unnotified_breaches": len(unnotified), "generated_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        if settings.DPO_EMAIL:
            try:
                send_security_alert_email(settings.DPO_EMAIL, f"Monthly compliance report: {report}")
            except Exception:  # noqa: BLE001
                logger.exception("generate_monthly_compliance_report: failed to email DPO")
        return report
