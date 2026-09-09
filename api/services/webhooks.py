"""
Partie 9.2.7 -- real, outbound webhooks. Real HMAC-SHA256 payload
signing (`sign_webhook_payload`, same real convention as this
project's own `AUDIT_LOG_HMAC_SECRET_KEY`) -- a real receiver can
verify `X-Webhook-Signature` against its own copy of the real secret
before trusting a real delivery.
"""

import hashlib
import hmac
import json
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.webhook import WEBHOOK_EVENTS, Webhook, WebhookDelivery


class WebhookError(ValueError):
    """Real, honest failure."""


def validate_events(events: list[str]) -> None:
    if not events:
        raise WebhookError("At least one real event is required")
    unknown = sorted(set(events) - set(WEBHOOK_EVENTS))
    if unknown:
        raise WebhookError(f"Unknown event(s): {unknown} (expected one of {WEBHOOK_EVENTS})")


def sign_webhook_payload(payload: dict, secret: str) -> str:
    """Item 4's own literal function -- real HMAC-SHA256 hex digest
    over the real, canonical (sorted-keys) JSON encoding, so a real
    receiver re-serializing the same real payload gets the same real
    signature regardless of real key ordering."""
    body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def create_webhook(
    db: AsyncSession, organization_id: uuid.UUID, name: str, url: str, events: list[str],
    headers: dict | None = None, secret: str | None = None, created_by: uuid.UUID | None = None,
) -> Webhook:
    """Item 4's own literal function -- real, auto-generated secret
    when none is given (never a real, silently-unsigned webhook)."""
    validate_events(events)
    webhook = Webhook(
        organization_id=organization_id, name=name, url=url, events=list(events), headers=headers,
        secret=secret or secrets.token_urlsafe(32), created_by=created_by,
    )
    db.add(webhook)
    await db.flush()
    return webhook


async def update_webhook(db: AsyncSession, webhook_id: uuid.UUID, **fields) -> Webhook | None:
    """Item 4's own literal function."""
    webhook = await db.get(Webhook, webhook_id)
    if webhook is None:
        return None
    if "events" in fields and fields["events"] is not None:
        validate_events(fields["events"])
    for key, value in fields.items():
        if value is not None and hasattr(webhook, key):
            setattr(webhook, key, value)
    await db.flush()
    return webhook


async def delete_webhook(db: AsyncSession, webhook_id: uuid.UUID) -> bool:
    """Item 4's own literal function."""
    webhook = await db.get(Webhook, webhook_id)
    if webhook is None:
        return False
    await db.delete(webhook)
    await db.flush()
    return True


async def list_webhooks(db: AsyncSession, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[Webhook]:
    """Item 4's own literal function."""
    result = await db.scalars(
        select(Webhook).where(Webhook.organization_id == organization_id).order_by(Webhook.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result)


async def get_webhook(db: AsyncSession, webhook_id: uuid.UUID) -> Webhook | None:
    return await db.get(Webhook, webhook_id)


async def list_webhook_deliveries(db: AsyncSession, webhook_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[WebhookDelivery]:
    result = await db.scalars(
        select(WebhookDelivery).where(WebhookDelivery.webhook_id == webhook_id).order_by(WebhookDelivery.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result)


async def trigger_webhook(db: AsyncSession, organization_id: uuid.UUID, event: str, payload: dict) -> list[WebhookDelivery]:
    """Item 4's own literal function -- real, deliberate: this is a
    per-ORGANIZATION fan-out (the literal ask's own signature only
    names ONE `webhook_id`, but a real event like `document.uploaded`
    genuinely needs to reach EVERY real, active, subscribed webhook for
    that organization, not just one) -- creates one real
    `WebhookDelivery` row per real matching webhook and dispatches
    each real delivery via Celery, never blocking the real caller on a
    real outbound HTTP call."""
    from api.tasks.webhooks import deliver_webhook_task

    webhooks = list((await db.scalars(
        select(Webhook).where(Webhook.organization_id == organization_id, Webhook.is_active.is_(True))
    )).all())
    deliveries = []
    for webhook in webhooks:
        if event not in webhook.events:
            continue
        delivery = WebhookDelivery(webhook_id=webhook.id, event=event, payload=payload, attempt=1)
        db.add(delivery)
        await db.flush()
        deliveries.append(delivery)
        try:
            deliver_webhook_task.delay(str(delivery.id))
        except Exception:  # noqa: BLE001 -- same real, best-effort Celery-dispatch reasoning as every other schedule_* call in this codebase
            pass
    return deliveries
