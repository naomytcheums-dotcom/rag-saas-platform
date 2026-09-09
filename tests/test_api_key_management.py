"""Partie 9.2.1 (API keys) + 9.2.2 (Rotation) + 9.2.3 (Expiration) +
9.2.4 (Scopes) + 9.2.5 (Rate limits) + 9.2.6 (Quotas)."""

import datetime as dt
import uuid

import pytest

from api.services.organization_api_keys import (
    OrganizationAPIKeyError, execute_scheduled_rotation, extend_key_expiration, generate_organization_api_key,
    get_api_key, get_available_scopes, get_due_scheduled_rotations, get_expired_active_keys, get_expiring_keys,
    get_key_rotation_history, get_keys_due_for_quota_reset, get_quota_status, get_rate_limit_status,
    increment_quota, is_key_expired, remove_key_expiration, reset_quota, rotate_api_key, schedule_key_rotation,
    set_key_expiration, set_quota, set_rate_limit, update_api_key, verify_api_key,
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
    org_id = (await client.post("/organizations", json={"name": "Key Mgmt Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id, user


# ------------------------------------------------------------------- 9.2.1 API keys


async def test_get_api_key(db_session):
    """Validation criterion: la récupération d'une clé fonctionne."""
    org_id = uuid.uuid4()
    row, _plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    fetched = await get_api_key(db_session, row.id)
    assert fetched is not None
    assert fetched.id == row.id
    assert fetched.is_active is True


async def test_update_api_key_name_and_scopes(db_session):
    """Validation criterion: la modification fonctionne."""
    org_id = uuid.uuid4()
    row, _plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    updated = await update_api_key(db_session, row.id, name="renamed", scopes=["chat:write", "search:read"])
    await db_session.commit()
    assert updated.name == "renamed"
    assert updated.scopes == ["chat:write", "search:read"]


async def test_update_api_key_is_active_deactivates_key(db_session):
    """Validation criterion: robustesse -- clé désactivée."""
    org_id = uuid.uuid4()
    row, plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    await update_api_key(db_session, row.id, is_active=False)
    await db_session.commit()

    assert await verify_api_key(db_session, plaintext) is None


async def test_update_api_key_rejects_invalid_scope(db_session):
    org_id = uuid.uuid4()
    row, _plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    with pytest.raises(OrganizationAPIKeyError):
        await update_api_key(db_session, row.id, scopes=["not-a-real-scope"])


async def test_get_api_key_endpoint(client, db_session, register_payload):
    token, org_id, _user = await _make_org(client, db_session, register_payload)
    created = await client.post(f"/organizations/{org_id}/api-keys", json={"name": "k1", "scopes": ["chat:write"]}, headers=_auth_header(token))
    key_id = created.json()["id"]

    response = await client.get(f"/api-keys/{key_id}", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["name"] == "k1"


async def test_patch_api_key_endpoint(client, db_session, register_payload):
    token, org_id, _user = await _make_org(client, db_session, register_payload)
    created = await client.post(f"/organizations/{org_id}/api-keys", json={"name": "k1", "scopes": ["chat:write"]}, headers=_auth_header(token))
    key_id = created.json()["id"]

    response = await client.patch(f"/api-keys/{key_id}", json={"name": "renamed"}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["name"] == "renamed"


# ------------------------------------------------------------------ 9.2.2 Key rotation


async def test_rotate_api_key_generates_new_key_and_revokes_old(db_session):
    """Validation criterion: la rotation fonctionne."""
    org_id = uuid.uuid4()
    old_row, old_plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    result = await rotate_api_key(db_session, old_row.id, rotated_by=uuid.uuid4(), reason="scheduled rotation")
    await db_session.commit()

    new_row, new_plaintext = result
    assert new_row.id != old_row.id
    assert new_row.scopes == old_row.scopes
    assert await verify_api_key(db_session, old_plaintext) is None
    assert await verify_api_key(db_session, new_plaintext) is not None


async def test_rotate_api_key_saves_history(db_session):
    """Validation criterion: l'historique est sauvegardé."""
    org_id = uuid.uuid4()
    old_row, _plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    new_row, _new_plaintext = await rotate_api_key(db_session, old_row.id, reason="test")
    await db_session.commit()

    history = await get_key_rotation_history(db_session, old_row.id)
    assert len(history) == 1
    assert history[0].rotated_from == old_row.id
    assert history[0].rotated_to == new_row.id
    assert history[0].reason == "test"


async def test_rotate_api_key_returns_none_for_unknown_key(db_session):
    assert await rotate_api_key(db_session, uuid.uuid4()) is None


async def test_rotate_api_key_endpoint(client, db_session, register_payload):
    token, org_id, _user = await _make_org(client, db_session, register_payload)
    created = await client.post(f"/organizations/{org_id}/api-keys", json={"name": "k1", "scopes": ["chat:write"]}, headers=_auth_header(token))
    key_id = created.json()["id"]

    response = await client.post(f"/api-keys/{key_id}/rotate", json={"reason": "manual"}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["key"].startswith("pk_")

    history = await client.get(f"/api-keys/{key_id}/rotation-history", headers=_auth_header(token))
    assert len(history.json()) == 1


# --------------------------------------------------------------- 9.2.3 Key expiration


async def test_is_key_expired(db_session):
    """Validation criterion: l'expiration fonctionne."""
    org_id = uuid.uuid4()
    row, _plaintext = await generate_organization_api_key(
        db_session, org_id, "key-1", ["chat:write"], expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
    )
    await db_session.commit()
    assert is_key_expired(row) is True


async def test_set_and_remove_key_expiration(db_session):
    org_id = uuid.uuid4()
    row, _plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=10)
    updated = await set_key_expiration(db_session, row.id, future)
    await db_session.commit()
    assert updated.expires_at is not None

    removed = await remove_key_expiration(db_session, row.id)
    await db_session.commit()
    assert removed.expires_at is None


async def test_extend_key_expiration(db_session):
    org_id = uuid.uuid4()
    future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=5)
    row, _plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"], expires_at=future)
    await db_session.commit()

    extended = await extend_key_expiration(db_session, row.id, 30)
    await db_session.commit()
    assert extended.expires_at > future


async def test_get_expiring_keys(db_session):
    """Validation criterion: les rappels d'expiration fonctionnent."""
    org_id = uuid.uuid4()
    soon = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=5)
    far = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=200)
    await generate_organization_api_key(db_session, org_id, "expiring-soon", ["chat:write"], expires_at=soon)
    await generate_organization_api_key(db_session, org_id, "expiring-later", ["chat:write"], expires_at=far)
    await db_session.commit()

    expiring = await get_expiring_keys(db_session, 30)
    assert len(expiring) == 1
    assert expiring[0].name == "expiring-soon"


# ------------------------------------------------------------------------- 9.2.4 Scopes


def test_get_available_scopes_matches_table():
    scopes = get_available_scopes()
    assert "chat:read" in scopes
    assert "embed:write" in scopes
    assert len(scopes) == 12


async def test_update_key_scopes_endpoint(client, db_session, register_payload):
    """Validation criterion: la modification des portées fonctionne."""
    token, org_id, _user = await _make_org(client, db_session, register_payload)
    created = await client.post(f"/organizations/{org_id}/api-keys", json={"name": "k1", "scopes": ["chat:write"]}, headers=_auth_header(token))
    key_id = created.json()["id"]

    response = await client.patch(f"/api-keys/{key_id}/scopes", json={"scopes": ["chat:read", "search:read"]}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["scopes"] == ["chat:read", "search:read"]


async def test_list_available_scopes_endpoint(client, db_session, register_payload):
    token, _org_id, _user = await _make_org(client, db_session, register_payload)
    response = await client.get("/api-keys/scopes", headers=_auth_header(token))
    assert response.status_code == 200
    assert len(response.json()["scopes"]) == 12


# ------------------------------------------------------------------- 9.2.5 Rate limits


async def test_set_and_get_rate_limit(db_session):
    """Validation criterion: la définition de limite fonctionne."""
    org_id = uuid.uuid4()
    row, _plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    updated = await set_rate_limit(db_session, row.id, 100, "hour")
    await db_session.commit()
    status_dict = await get_rate_limit_status(updated)
    assert status_dict == {"rate_limit": 100, "rate_limit_period": "hour"}


async def test_set_rate_limit_rejects_invalid_period(db_session):
    org_id = uuid.uuid4()
    row, _plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    with pytest.raises(OrganizationAPIKeyError):
        await set_rate_limit(db_session, row.id, 100, "not-a-real-period")


# ----------------------------------------------------------------------- 9.2.6 Quotas


async def test_set_quota_and_check_status(db_session):
    """Validation criterion: le quota fonctionne."""
    org_id = uuid.uuid4()
    row, _plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    updated = await set_quota(db_session, row.id, 100, "month")
    await db_session.commit()
    assert updated.quota_limit == 100
    assert updated.quota_reset_at is not None


async def test_increment_quota_and_enforce_limit(monkeypatch, client, db_session, register_payload):
    """Validation criterion: robustesse -- quota atteint."""
    from unittest.mock import AsyncMock

    monkeypatch.setattr("api.services.embedding_providers.get_embedding", AsyncMock(return_value=[0.1, 0.2]))

    token, org_id, _user = await _make_org(client, db_session, register_payload)
    created = await client.post(f"/organizations/{org_id}/api-keys", json={"name": "k1", "scopes": ["embed:write"]}, headers=_auth_header(token))
    key_id = created.json()["id"]
    await client.patch(f"/api-keys/{key_id}/quota", json={"limit": 1, "period": "month"}, headers=_auth_header(token))
    api_key = created.json()["key"]

    first = await client.post("/v1/embed", json={"text": "hello"}, headers={"X-API-Key": api_key})
    assert first.status_code == 200

    second = await client.post("/v1/embed", json={"text": "hello again"}, headers={"X-API-Key": api_key})
    assert second.status_code == 429


async def test_schedule_and_execute_rotation(db_session):
    """Validation criterion: les rotations planifiées fonctionnent."""
    org_id = uuid.uuid4()
    row, _plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    due = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    await schedule_key_rotation(db_session, row.id, due)
    await db_session.commit()

    assert len(await get_due_scheduled_rotations(db_session)) == 1

    result = await execute_scheduled_rotation(db_session, row.id)
    await db_session.commit()
    assert result is not None
    new_row, _new_plaintext = result
    assert new_row.id != row.id


async def test_execute_scheduled_rotation_no_op_when_not_due(db_session):
    org_id = uuid.uuid4()
    row, _plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
    await schedule_key_rotation(db_session, row.id, future)
    await db_session.commit()

    assert await execute_scheduled_rotation(db_session, row.id) is None


async def test_get_expired_active_keys(db_session):
    """Validation criterion: robustesse -- clés expirées détectées."""
    org_id = uuid.uuid4()
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    await generate_organization_api_key(db_session, org_id, "expired-key", ["chat:write"], expires_at=past)
    await db_session.commit()

    expired = await get_expired_active_keys(db_session)
    assert len(expired) == 1
    assert expired[0].name == "expired-key"


async def test_get_keys_due_for_quota_reset(db_session):
    org_id = uuid.uuid4()
    row, _plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()
    await set_quota(db_session, row.id, 100, "month")
    row.quota_reset_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    await db_session.commit()

    due = await get_keys_due_for_quota_reset(db_session)
    assert len(due) == 1


async def test_reset_quota(db_session):
    org_id = uuid.uuid4()
    row, _plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()
    await set_quota(db_session, row.id, 10, "month")
    await increment_quota(db_session, row, 5)
    await db_session.commit()

    reset_row = await reset_quota(db_session, row.id)
    await db_session.commit()
    assert reset_row.quota_used == 0
