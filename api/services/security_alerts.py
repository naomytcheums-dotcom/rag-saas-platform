"""
Audit finding 21 -- real-time alerting when failed-login attempts spike,
on top of the per-account email api/services/email.py's
send_rate_limit_alert_email already sends (that one tells the ACCOUNT
OWNER; this tells an operator/security team, and fires on volume alone,
independent of whether any single account's own rate limit tripped --
a distributed attack spread across many different target accounts,
none individually hitting LOGIN_RATE_LIMIT_MAX_ATTEMPTS, would
otherwise go completely unnoticed operationally).

Two channels, either/both/neither configurable (api/config.py):
- SECURITY_ALERT_WEBHOOK_URL: a Slack-compatible incoming webhook
  ({"text": "..."} POST body -- also accepted by most Slack-compatible
  relays for other chat tools).
- SECURITY_ALERT_EMAIL: a plain transactional email via the existing
  Resend integration (api/services/email.py's send_security_alert_email).

Fails open/quiet on any delivery error (same reasoning as every other
optional external integration in this codebase, e.g. api/security/
rate_limit.py's Redis handling) -- a webhook or SMTP outage must never
be what breaks login itself.
"""

import asyncio
import datetime as dt
import logging

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.audit_log import AuditAction, AuditLog
from api.services.email import send_security_alert_email

logger = logging.getLogger(__name__)

_WEBHOOK_TIMEOUT_SECONDS = 5.0


def _send_webhook_alert_sync(message: str) -> None:
    if not settings.SECURITY_ALERT_WEBHOOK_URL:
        return
    try:
        response = httpx.post(settings.SECURITY_ALERT_WEBHOOK_URL, json={"text": message}, timeout=_WEBHOOK_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("failed to deliver security alert webhook: %s", exc)


async def _send_webhook_alert(message: str) -> None:
    # Real bug fixed here (2026-09-15): httpx.post is the sync, blocking
    # client -- calling it directly from this async call chain blocked
    # the event loop for up to _WEBHOOK_TIMEOUT_SECONDS. Same class of
    # bug as api/services/email.py's send_*_email functions (see
    # api/services/verification.py's docstring for the full incident).
    await asyncio.to_thread(_send_webhook_alert_sync, message)


async def _send_email_alert(message: str) -> None:
    if not settings.SECURITY_ALERT_EMAIL:
        return
    try:
        await asyncio.to_thread(send_security_alert_email, settings.SECURITY_ALERT_EMAIL, message)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to deliver security alert email: %s", exc)


async def check_and_alert_on_failed_login_spike(db: AsyncSession, ip: str | None, email: str) -> None:
    """
    Called by api/routers/auth.py's login() after every failed attempt is
    logged to the audit trail. Counts LOGIN_FAILED rows in the last
    SECURITY_ALERT_WINDOW_MINUTES, separately by IP and by targeted
    email -- either crossing SECURITY_ALERT_FAILED_LOGIN_THRESHOLD fires
    an alert (a distributed attack against one account from many IPs,
    and a single IP spraying many accounts, are both real patterns worth
    catching, and neither implies the other).

    Fires exactly once per spike, not once per attempt past the
    threshold: only when the count is EXACTLY at the threshold (the
    request that just crossed the line), so a sustained attack doesn't
    spam the alert channel with one message per additional failed
    attempt.
    """
    window_start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=settings.SECURITY_ALERT_WINDOW_MINUTES)

    ip_count = 0
    if ip:
        ip_count = await db.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.action == AuditAction.LOGIN_FAILED.value, AuditLog.ip == ip, AuditLog.timestamp >= window_start,
            )
        ) or 0

    email_count = await db.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == AuditAction.LOGIN_FAILED.value,
            AuditLog.timestamp >= window_start,
            AuditLog.metadata_json.contains(email),  # metadata_json is a JSON *string* column -- see AuditLog's docstring
        )
    ) or 0

    threshold = settings.SECURITY_ALERT_FAILED_LOGIN_THRESHOLD
    if ip_count == threshold:
        # Plain text, deliberately -- this same string goes to a Slack-
        # compatible webhook (no HTML interpretation there) AND to
        # send_security_alert_email, which does its own HTML-escaping
        # for the email channel. Pre-escaping here would double-escape
        # it for email while breaking the plain-text webhook rendering.
        message = f"{threshold} failed login attempts from IP {ip} in the last {settings.SECURITY_ALERT_WINDOW_MINUTES} minutes."
        await asyncio.gather(_send_webhook_alert(message), _send_email_alert(message))
    if email_count == threshold:
        message = f"{threshold} failed login attempts targeting {email} in the last {settings.SECURITY_ALERT_WINDOW_MINUTES} minutes."
        await asyncio.gather(_send_webhook_alert(message), _send_email_alert(message))
