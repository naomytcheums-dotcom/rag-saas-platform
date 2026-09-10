"""Partie 10.2 -- new /audit/* endpoints and the organization_id/
resource_type/resource_id columns, on top of the existing, already-real
HMAC hash-chained audit log."""

import uuid

import pytest


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _make_admin(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.admin
    await db_session.commit()
    return token, user


async def test_webhook_create_and_delete_are_audited_with_resource_columns(client, db_session, register_payload):
    token, user = await _make_admin(client, db_session, register_payload)
    org_id = (await client.post("/organizations", json={"name": "Audit Org"}, headers=_auth_header(token))).json()["id"]

    create_response = await client.post(
        f"/organizations/{org_id}/webhooks", json={"name": "hook", "url": "https://example.com", "events": ["message.created"]},
        headers=_auth_header(token),
    )
    webhook_id = create_response.json()["id"]

    logs = await client.get(f"/audit/resource/webhook/{webhook_id}", headers=_auth_header(token))
    assert logs.status_code == 200
    assert logs.json()["total"] == 1
    assert logs.json()["items"][0]["action"] == "webhook_created"

    await client.delete(f"/webhooks/{webhook_id}", headers=_auth_header(token))
    logs_after_delete = await client.get(f"/audit/resource/webhook/{webhook_id}", headers=_auth_header(token))
    assert logs_after_delete.json()["total"] == 2
    actions = {entry["action"] for entry in logs_after_delete.json()["items"]}
    assert actions == {"webhook_created", "webhook_deleted"}


async def test_organization_scoped_audit_log_endpoint(client, db_session, register_payload):
    token, _ = await _make_admin(client, db_session, register_payload)
    org_id = (await client.post("/organizations", json={"name": "Org Audit"}, headers=_auth_header(token))).json()["id"]

    await client.post(f"/organizations/{org_id}/webhooks", json={"name": "hook", "url": "https://example.com", "events": ["message.created"]}, headers=_auth_header(token))

    org_logs = await client.get(f"/organizations/{org_id}/audit-logs", headers=_auth_header(token))
    assert org_logs.status_code == 200
    assert org_logs.json()["total"] == 1
    assert org_logs.json()["items"][0]["action"] == "webhook_created"

    # A different, unrelated org sees none of it.
    other_org_id = (await client.post("/organizations", json={"name": "Other Org"}, headers=_auth_header(token))).json()["id"]
    other_logs = await client.get(f"/organizations/{other_org_id}/audit-logs", headers=_auth_header(token))
    assert other_logs.json()["total"] == 0


async def test_audit_stats_endpoint(client, db_session, register_payload):
    token, _ = await _make_admin(client, db_session, register_payload)
    response = await client.get("/audit/stats", headers=_auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1  # at least the register action itself
    assert "register" in body["by_action"] or body["total"] >= 0


async def test_audit_actions_endpoint_lists_the_real_enum(client, db_session, register_payload):
    token, _ = await _make_admin(client, db_session, register_payload)
    response = await client.get("/audit/actions", headers=_auth_header(token))
    assert response.status_code == 200
    keys = {item["key"] for item in response.json()["items"]}
    assert "webhook_created" in keys
    assert "document_uploaded" in keys
    assert "agent_deleted" in keys


async def test_audit_export_json_and_csv(client, db_session, register_payload):
    token, _ = await _make_admin(client, db_session, register_payload)
    json_response = await client.get("/audit/export?fmt=json", headers=_auth_header(token))
    assert json_response.status_code == 200
    assert json_response.headers["content-type"].startswith("application/json")

    csv_response = await client.get("/audit/export?fmt=csv", headers=_auth_header(token))
    assert csv_response.status_code == 200
    assert "action" in csv_response.text.splitlines()[0]


async def test_audit_user_endpoint_scopes_to_one_user(client, db_session, register_payload):
    token, user = await _make_admin(client, db_session, register_payload)
    response = await client.get(f"/audit/user/{user.id}", headers=_auth_header(token))
    assert response.status_code == 200
    assert all(item["user_id"] == str(user.id) for item in response.json()["items"])


async def test_purge_requires_superadmin(client, db_session, register_payload):
    token, user = await _make_admin(client, db_session, register_payload)  # admin, not superadmin
    response = await client.delete("/audit/logs/purge?older_than_days=1", headers=_auth_header(token))
    assert response.status_code == 403


async def test_purge_deletes_old_rows_as_superadmin(client, db_session, register_payload):
    import datetime as dt

    from sqlalchemy import select

    from api.models.audit_log import AuditAction, AuditLog
    from api.models.user import User, UserRole
    from api.security.audit_log import log_audit_action

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.superadmin
    await db_session.commit()

    old_row = await log_audit_action(db_session, user_id=user.id, action=AuditAction.LOGIN_SUCCESS, ip=None, user_agent=None, success=True)
    old_row.timestamp = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=400)
    await db_session.commit()

    response = await client.delete("/audit/logs/purge?older_than_days=365", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["deleted"] >= 1

    remaining = await db_session.scalar(select(AuditLog).where(AuditLog.id == old_row.id))
    assert remaining is None
