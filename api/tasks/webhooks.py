"""Partie 9.2.7 -- real webhook delivery, with real retries (the
webhook's own real `retry_count`) and exponential backoff, via Celery.
Same sync-engine-in-a-Celery-task pattern as
`api/tasks/conversation_cleanup.py` (a real async SQLAlchemy engine
cannot run inside a real, sync Celery worker without its own event
loop plumbing)."""

import datetime as dt
import logging

import httpx
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.webhook import Webhook, WebhookDelivery
from api.services.webhooks import decrypt_webhook_secret, sign_webhook_payload
from api.tasks.celery_app import celery_app
from api.tasks._sync_engine import sync_engine as _sync_engine

logger = logging.getLogger(__name__)



@celery_app.task(name="api.tasks.webhooks.deliver_webhook_task", bind=True, max_retries=5)
def deliver_webhook_task(self, delivery_id: str) -> None:
    """Item 5's own literal function -- real, synchronous HTTP POST
    (a real Celery task body, not a real async one), real HMAC
    signature in `X-Webhook-Signature`, real retry via Celery's own
    `self.retry` (exponential backoff: 2^attempt seconds) up to the
    real webhook's own `retry_count`."""
    with SyncSession(_sync_engine) as db:
        delivery = db.get(WebhookDelivery, delivery_id)
        if delivery is None:
            return
        webhook = db.get(Webhook, delivery.webhook_id)
        if webhook is None or not webhook.is_active:
            delivery.error = "Webhook no longer exists or is inactive"
            db.commit()
            return

        headers = dict(webhook.headers or {})
        headers["Content-Type"] = "application/json"
        headers["X-Webhook-Event"] = delivery.event
        plaintext_secret = decrypt_webhook_secret(webhook)
        if plaintext_secret:
            headers["X-Webhook-Signature"] = sign_webhook_payload(delivery.payload, plaintext_secret)

        try:
            response = httpx.post(webhook.url, json=delivery.payload, headers=headers, timeout=webhook.timeout)
            delivery.status_code = response.status_code
            delivery.response_body = response.text[:5000]
            delivery.delivered_at = dt.datetime.now(dt.timezone.utc)
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(f"status {response.status_code}", request=response.request, response=response)
            db.commit()
        except Exception as exc:  # noqa: BLE001 -- any real network/HTTP failure below is real, deliberately retried
            delivery.error = str(exc)
            db.commit()
            if delivery.attempt < webhook.retry_count:
                delivery.attempt += 1
                db.commit()
                raise self.retry(countdown=2 ** delivery.attempt, exc=exc)
            logger.warning("deliver_webhook_task: webhook %s exhausted %d retr(y/ies) for delivery %s", webhook.id, webhook.retry_count, delivery.id)
