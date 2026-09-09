"""Partie 9.2.7 -- Webhooks."""

import uuid
from unittest.mock import patch

import pytest

from api.services.webhooks import (
    WebhookError, create_webhook, delete_webhook, sign_webhook_payload, trigger_webhook, update_webhook,
    validate_events,
)


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    from sqlalchemy import select

    from api.models.user import User

    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org(client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": "Webhook Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id, user


# --------------------------------------------------------------------- Unit


def test_validate_events_rejects_unknown_event():
    with pytest.raises(WebhookError):
        validate_events(["not.a.real.event"])


def test_sign_webhook_payload_is_deterministic():
    """Validation criterion: sécurité -- les payloads sont signés."""
    payload = {"b": 2, "a": 1}
    signature1 = sign_webhook_payload(payload, "secret")
    signature2 = sign_webhook_payload({"a": 1, "b": 2}, "secret")
    assert signature1 == signature2
    assert len(signature1) == 64  # real SHA-256 hex digest


def test_sign_webhook_payload_differs_per_secret():
    payload = {"a": 1}
    assert sign_webhook_payload(payload, "secret1") != sign_webhook_payload(payload, "secret2")


async def test_create_webhook_generates_secret_when_none_given(db_session):
    """Validation criterion: la création de webhook fonctionne."""
    org_id = uuid.uuid4()
    webhook = await create_webhook(db_session, org_id, "My webhook", "https://example.com/hook", ["message.created"])
    await db_session.commit()
    assert webhook.secret is not None
    assert len(webhook.secret) > 20


async def test_create_webhook_rejects_unknown_event(db_session):
    org_id = uuid.uuid4()
    with pytest.raises(WebhookError):
        await create_webhook(db_session, org_id, "My webhook", "https://example.com/hook", ["not.a.real.event"])


async def test_update_webhook(db_session):
    org_id = uuid.uuid4()
    webhook = await create_webhook(db_session, org_id, "My webhook", "https://example.com/hook", ["message.created"])
    await db_session.commit()

    updated = await update_webhook(db_session, webhook.id, name="renamed", is_active=False)
    await db_session.commit()
    assert updated.name == "renamed"
    assert updated.is_active is False


async def test_delete_webhook(db_session):
    org_id = uuid.uuid4()
    webhook = await create_webhook(db_session, org_id, "My webhook", "https://example.com/hook", ["message.created"])
    await db_session.commit()

    deleted = await delete_webhook(db_session, webhook.id)
    await db_session.commit()
    assert deleted is True


async def test_trigger_webhook_creates_delivery_and_dispatches_task(db_session):
    """Validation criterion: le déclenchement fonctionne (async/Celery)."""
    org_id = uuid.uuid4()
    await create_webhook(db_session, org_id, "My webhook", "https://example.com/hook", ["message.created"])
    await db_session.commit()

    with patch("api.tasks.webhooks.deliver_webhook_task.delay") as mock_delay:
        deliveries = await trigger_webhook(db_session, org_id, "message.created", {"text": "hi"})
        await db_session.commit()

    assert len(deliveries) == 1
    mock_delay.assert_called_once()


async def test_trigger_webhook_skips_unsubscribed_event(db_session):
    org_id = uuid.uuid4()
    await create_webhook(db_session, org_id, "My webhook", "https://example.com/hook", ["message.created"])
    await db_session.commit()

    with patch("api.tasks.webhooks.deliver_webhook_task.delay"):
        deliveries = await trigger_webhook(db_session, org_id, "document.uploaded", {"id": "doc1"})
        await db_session.commit()

    assert deliveries == []


async def test_send_test_delivery_dispatches_regardless_of_event_subscription(db_session):
    """Validation criterion: le bouton "Test" du dashboard fonctionne
    même pour un webhook non abonné à un vrai événement -- un test
    manuel est un envoi délibéré, pas un vrai événement plateforme."""
    from api.services.webhooks import send_test_delivery

    org_id = uuid.uuid4()
    webhook = await create_webhook(db_session, org_id, "My webhook", "https://example.com/hook", ["document.uploaded"])
    await db_session.commit()

    with patch("api.tasks.webhooks.deliver_webhook_task.delay") as mock_delay:
        delivery = await send_test_delivery(db_session, webhook)
        await db_session.commit()

    assert delivery.event == "test"
    assert delivery.webhook_id == webhook.id
    mock_delay.assert_called_once_with(str(delivery.id))


# ---------------------------------------------------------------------- Endpoints


async def test_webhook_crud_endpoints(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    token, org_id, _user = await _make_org(client, db_session, register_payload)

    created = await client.post(
        f"/organizations/{org_id}/webhooks", json={"name": "hook1", "url": "https://example.com/hook", "events": ["message.created"]},
        headers=_auth_header(token),
    )
    assert created.status_code == 200
    webhook_id = created.json()["id"]

    listing = await client.get(f"/organizations/{org_id}/webhooks", headers=_auth_header(token))
    assert len(listing.json()) == 1

    fetched = await client.get(f"/webhooks/{webhook_id}", headers=_auth_header(token))
    assert fetched.status_code == 200

    updated = await client.patch(f"/webhooks/{webhook_id}", json={"name": "renamed"}, headers=_auth_header(token))
    assert updated.json()["name"] == "renamed"

    deleted = await client.delete(f"/webhooks/{webhook_id}", headers=_auth_header(token))
    assert deleted.status_code == 204


async def test_webhook_endpoints_reject_non_admin_of_other_org(client, db_session, register_payload):
    token, org_id, _user = await _make_org(client, db_session, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/webhooks", json={"name": "hook1", "url": "https://example.com/hook", "events": ["message.created"]},
        headers=_auth_header(token),
    )
    webhook_id = created.json()["id"]

    other_token, _other_user = await _register(client, db_session, "other-webhook@example.com")
    response = await client.get(f"/webhooks/{webhook_id}", headers=_auth_header(other_token))
    assert response.status_code == 404


async def test_webhook_test_endpoint(client, db_session, register_payload, monkeypatch):
    """Validation criterion: real, end-to-end -- POST /webhooks/{id}/test
    creates a real delivery row and dispatches it, mocked here the same
    way test_webhook_crud_endpoints's own sibling tests mock Celery."""
    from unittest.mock import MagicMock

    monkeypatch.setattr("api.tasks.webhooks.deliver_webhook_task.delay", MagicMock())

    token, org_id, _user = await _make_org(client, db_session, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/webhooks", json={"name": "hook1", "url": "https://example.com/hook", "events": ["message.created"]},
        headers=_auth_header(token),
    )
    webhook_id = created.json()["id"]

    response = await client.post(f"/webhooks/{webhook_id}/test", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["event"] == "test"
