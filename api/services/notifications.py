"""
Phase 5, Étape 4 -- the real notification service: creation
(respecting preferences), listing, read/unread, preferences CRUD, and
real-time publish. Real-time reuses this codebase's OWN existing
Redis pub/sub pattern (api/security/documents.py's
send_progress_update/stream_document_progress, itself built on
`RATE_LIMIT_REDIS_URL`, the same real Redis this codebase already runs
for rate limiting) rather than inventing a second one -- no new
infrastructure, same "fix the incoherence, don't duplicate it"
discipline as every prior étape this session.

**Email branding correction (deferred from Étape 3)**: notification
emails are composed through api/services/email_branding.py's own
`get_active_branding`/`compose_branded_from_address`/
`render_branded_header`/`render_branded_footer` -- the exact same
primitives Étape 3 wired into ONE email (organization invitations).
This is the second real call site, extending branding rather than
leaving it a one-off.
"""

import datetime as dt
import json
import logging
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.notification import Notification, NotificationPreference
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.redis_client import get_or_rebuild
from api.services.email_branding import (
    compose_branded_from_address, get_active_branding, render_branded_footer, render_branded_header,
)
from api.services.notification_templates import render_notification

logger = logging.getLogger(__name__)

# Defaults per the étape's own spec table -- every real trigger this
# étape wires defaults to "in-app + email" except workflow_completed
# (in-app only), matching that table exactly. A type not listed here
# defaults to "in-app + email" too (the safer default: a user who never
# customized preferences should not silently miss something).
_DEFAULT_CHANNELS: dict[str, set[str]] = {
    "workflow_completed": {"in_app"},
    # in-app only: api/security/sessions.py already sends a real,
    # purpose-formatted email (send_new_login_notification_email)
    # immediately before calling create_notification for this type --
    # letting create_notification ALSO email would double-send.
    "security_login_new_device": {"in_app"},
    # Same double-send reasoning: api/routers/account.py's own
    # send_password_changed_email and api/routers/two_factor.py's own
    # send_two_factor_enabled_email already send a real, dedicated
    # email immediately before each of these calls create_notification.
    "security_password_changed": {"in_app"},
    "security_2fa_enabled": {"in_app"},
}


def _default_channels_for(notification_type: str) -> set[str]:
    return _DEFAULT_CHANNELS.get(notification_type, {"in_app", "email"})


async def resolve_preference(db: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID | None, notification_type: str) -> tuple[bool, bool]:
    """Returns (in_app_enabled, email_enabled). No row means "use the
    real, honest default" for this type (see this module's own
    `_DEFAULT_CHANNELS`) -- never a silent False for a preference the
    user never actually set.

    `organization_id=None` (an account-level notification with no
    single owning org, e.g. `security_login_new_device`) always uses
    the hard default -- `NotificationPreference.organization_id` is
    NOT NULL (a preference genuinely needs one real org to be scoped
    to), so there is no row to look up for an org-less type. A user
    cannot customize an org-less notification type's channels in this
    étape's own scope -- traced in ROADMAP.md, not silently missing."""
    if organization_id is None:
        defaults = _default_channels_for(notification_type)
        return "in_app" in defaults, "email" in defaults

    pref = await db.scalar(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.organization_id == organization_id,
            NotificationPreference.notification_type == notification_type,
        )
    )
    if pref is not None:
        return pref.in_app_enabled, pref.email_enabled
    defaults = _default_channels_for(notification_type)
    return "in_app" in defaults, "email" in defaults


async def get_org_owner_user_id(db: AsyncSession, organization_id: uuid.UUID) -> uuid.UUID | None:
    """Real, honest resolution: the org's own current Owner, or None if
    somehow absent (e.g. a test fixture that never assigns one) --
    callers must treat None as "nobody to notify", never crash."""
    return await db.scalar(
        select(OrganizationMember.user_id).where(
            OrganizationMember.organization_id == organization_id, OrganizationMember.role == OrganizationRole.owner,
        )
    )


async def notify_billing_payment_failed(db: AsyncSession, organization_id: uuid.UUID) -> None:
    """Phase 5, Étape 4 -- the one real trigger for the "billing"
    domain, called from BOTH api/services/billing_stripe.py and
    api/services/billing_paystack.py's own `invoice.payment_failed`
    webhook handling -- one real function, not duplicated per
    provider."""
    from api.models.organization import Organization

    owner_id = await get_org_owner_user_id(db, organization_id)
    if owner_id is None:
        return
    organization = await db.get(Organization, organization_id)
    await create_notification(
        db, organization_id=organization_id, user_id=owner_id, notification_type="billing_payment_failed",
        priority="urgent", context={"organization_name": organization.name if organization else str(organization_id)},
    )


# -- real-time (Redis pub/sub, reusing api/security/documents.py's own pattern) --

_redis = None
_redis_loop = None


def _get_notification_redis():
    global _redis, _redis_loop
    from api.config import settings

    _redis, _redis_loop = get_or_rebuild(_redis, _redis_loop, settings.RATE_LIMIT_REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
    return _redis


def _channel_for(user_id: uuid.UUID) -> str:
    return f"notifications:{user_id}"


async def _publish_realtime(notification: Notification) -> None:
    try:
        await _get_notification_redis().publish(
            _channel_for(notification.user_id),
            json.dumps({
                "id": str(notification.id), "type": notification.type, "title": notification.title,
                "body": notification.body, "priority": notification.priority, "created_at": notification.created_at.isoformat() if notification.created_at else None,
            }),
        )
    except Exception as exc:  # noqa: BLE001 -- a broker hiccup must never break real notification creation
        logger.warning("_publish_realtime: could not publish notification '%s' for user '%s': %s", notification.id, notification.user_id, exc)


async def stream_user_notifications(user_id: uuid.UUID, db=None):
    """Real async generator wrapped in a StreamingResponse by
    api/routers/notification_center.py's own SSE route.

    Phase 5, Étape 4bis -- sends a real, initial snapshot of the user's
    own unread notifications (so a reconnecting client never misses
    what happened while it was offline), then streams real new
    notifications via Redis pub/sub for what happens next."""
    # Real, initial replay: unread notifications for this user
    if db is not None:
        from api.models.notification import Notification
        from sqlalchemy import select

        result = await db.execute(
            select(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
        for notification in result.scalars().all():
            payload = {
                "id": str(notification.id),
                "type": notification.notification_type,
                "title": notification.title,
                "body": notification.body,
                "priority": notification.priority,
                "created_at": notification.created_at.isoformat() if notification.created_at else None,
            }
            import json as _json
            yield f"event: snapshot\ndata: {_json.dumps(payload)}\n\n"

    pubsub = _get_notification_redis().pubsub()
    channel = _channel_for(user_id)
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            yield f"event: notification\ndata: {message['data']}\n\n"
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


# -- creation --------------------------------------------------------------

async def create_notification(
    db: AsyncSession, *, organization_id: uuid.UUID | None, user_id: uuid.UUID, notification_type: str,
    context: dict, priority: str = "normal", expires_at=None,
) -> Notification | None:
    """The one real entry point every trigger (job completion, billing
    webhook, workflow run, invitation, login) calls. Returns None (and
    creates nothing) if BOTH channels are disabled for this user/type --
    a real, honest "nothing to send" rather than an empty row that
    exists only to immediately look ignored.

    `context` is passed straight to Jinja2
    (api/services/notification_templates.render_notification) --
    callers own supplying whatever keys their own type's template
    needs (e.g. `document_name`, `organization_name`)."""
    in_app_enabled, email_enabled = await resolve_preference(db, user_id, organization_id, notification_type)
    if not in_app_enabled and not email_enabled:
        return None

    rendered = render_notification(notification_type, context)
    channel = "both" if (in_app_enabled and email_enabled) else ("in_app" if in_app_enabled else "email")

    notification = Notification(
        organization_id=organization_id, user_id=user_id, type=notification_type,
        title=rendered["title"], body=rendered["body"], data=context, priority=priority,
        channel=channel, expires_at=expires_at, email_status="pending" if email_enabled else "skipped",
    )
    db.add(notification)
    await db.flush()

    if in_app_enabled:
        await _publish_realtime(notification)

    if email_enabled:
        from api.tasks.notifications import send_notification_email_task

        try:
            send_notification_email_task.delay(str(notification.id))
        except Exception as exc:  # noqa: BLE001 -- a broker hiccup must never fail the real notification that already persisted
            logger.warning("create_notification: could not schedule email for '%s': %s", notification.id, exc)

    return notification


async def send_notification_email(db: AsyncSession, notification_id: uuid.UUID) -> None:
    """Real send, called by the Celery task (api/tasks/notifications.py).
    Idempotent against a notification whose email was already sent or
    deliberately skipped -- a retried/duplicated task invocation is a
    real possibility (Celery, like every real broker, guarantees
    at-least-once delivery) and must never double-send."""
    from api.services.email import _send

    notification = await db.get(Notification, notification_id)
    if notification is None or notification.email_status != "pending":
        return

    user = await db.get(User, notification.user_id)
    if user is None:
        notification.email_status = "failed"
        notification.email_error = "recipient user no longer exists"
        await db.flush()
        return

    rendered = render_notification(notification.type, notification.data or {})
    branding = await get_active_branding(db, notification.organization_id)
    body = f"{render_branded_header(branding)}<p>{notification.body}</p>{render_branded_footer(branding)}"

    try:
        _send(user.email, rendered["email_subject"], body, compose_branded_from_address(branding))
        notification.email_status = "sent"
        notification.email_sent_at = dt.datetime.now(dt.timezone.utc)
    except Exception as exc:  # noqa: BLE001 -- a real send failure is recorded on the row, not raised past this point
        notification.email_status = "failed"
        notification.email_error = str(exc)
        notification.email_retry_count += 1
        logger.warning("send_notification_email: failed to send notification '%s' to user '%s': %s", notification.id, notification.user_id, exc)
    await db.flush()


# -- read/list/preferences ---------------------------------------------------

async def list_notifications(db: AsyncSession, user_id: uuid.UUID, *, organization_id: uuid.UUID | None = None, unread_only: bool = False, limit: int = 50, offset: int = 0) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if organization_id is not None:
        stmt = stmt.where(Notification.organization_id == organization_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    return list((await db.scalars(stmt)).all())


async def get_unread_count(db: AsyncSession, user_id: uuid.UUID, *, organization_id: uuid.UUID | None = None) -> int:
    stmt = select(Notification.id).where(Notification.user_id == user_id, Notification.read_at.is_(None))
    if organization_id is not None:
        stmt = stmt.where(Notification.organization_id == organization_id)
    return len((await db.scalars(stmt)).all())


class NotificationNotFoundError(Exception):
    pass


async def mark_read(db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification:
    notification = await db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id))
    if notification is None:
        raise NotificationNotFoundError(str(notification_id))
    if notification.read_at is None:
        notification.read_at = dt.datetime.now(dt.timezone.utc)
        await db.flush()
    return notification


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID, *, organization_id: uuid.UUID | None = None) -> int:
    stmt = update(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
    if organization_id is not None:
        stmt = stmt.where(Notification.organization_id == organization_id)
    stmt = stmt.values(read_at=dt.datetime.now(dt.timezone.utc))
    result = await db.execute(stmt)
    return result.rowcount or 0


async def delete_notification(db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID) -> None:
    notification = await db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id))
    if notification is None:
        raise NotificationNotFoundError(str(notification_id))
    await db.delete(notification)
    await db.flush()


async def get_preferences(db: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID) -> list[NotificationPreference]:
    return list((await db.scalars(select(NotificationPreference).where(NotificationPreference.user_id == user_id, NotificationPreference.organization_id == organization_id))).all())


async def update_preference(db: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID, notification_type: str, *, in_app_enabled: bool | None = None, email_enabled: bool | None = None) -> NotificationPreference:
    pref = await db.scalar(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id, NotificationPreference.organization_id == organization_id, NotificationPreference.notification_type == notification_type,
        )
    )
    if pref is None:
        default_in_app, default_email = "in_app" in _default_channels_for(notification_type), "email" in _default_channels_for(notification_type)
        pref = NotificationPreference(user_id=user_id, organization_id=organization_id, notification_type=notification_type, in_app_enabled=default_in_app, email_enabled=default_email)
        db.add(pref)
    if in_app_enabled is not None:
        pref.in_app_enabled = in_app_enabled
    if email_enabled is not None:
        pref.email_enabled = email_enabled
    await db.flush()
    return pref


async def notify_billing_quota_warning(
    db: AsyncSession, organization_id: uuid.UUID, usage: float, limit: float,
) -> None:
    """Real trigger for the "approaching quota" warning. Called when
    usage crosses the configured warning threshold (e.g. 80%)."""
    from api.models.organization import Organization

    owner_id = await get_org_owner_user_id(db, organization_id)
    if owner_id is None:
        return
    organization = await db.get(Organization, organization_id)
    await create_notification(
        db, organization_id=organization_id, user_id=owner_id, notification_type="billing_quota_warning",
        priority="normal",
        context={
            "organization_name": organization.name if organization else str(organization_id),
            "usage": usage,
            "limit": limit,
        },
    )


async def notify_billing_quota_exceeded(
    db: AsyncSession, organization_id: uuid.UUID, usage: float, limit: float,
) -> None:
    """Real trigger for the "quota exceeded" notification. Called when
    usage crosses the configured hard limit."""
    from api.models.organization import Organization

    owner_id = await get_org_owner_user_id(db, organization_id)
    if owner_id is None:
        return
    organization = await db.get(Organization, organization_id)
    await create_notification(
        db, organization_id=organization_id, user_id=owner_id, notification_type="billing_quota_exceeded",
        priority="urgent",
        context={
            "organization_name": organization.name if organization else str(organization_id),
            "usage": usage,
            "limit": limit,
        },
    )


async def notify_billing_payment_succeeded(db: AsyncSession, organization_id: uuid.UUID) -> None:
    """Real, additive: the "a real payment succeeded" notification --
    symmetric with notify_billing_payment_failed above. Real, honest
    no-op if the organization has no real owner to notify."""
    from api.models.organization import Organization, OrganizationMember

    org = await db.get(Organization, organization_id)
    if org is None:
        return
    owner = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.role == "owner",
        )
    )
    if owner is None:
        return
    await create_notification(
        db,
        user_id=owner.user_id,
        organization_id=organization_id,
        type="billing_payment_succeeded",
        title="Payment received",
        body=f"Your payment for {org.name} was received successfully.",
    )
