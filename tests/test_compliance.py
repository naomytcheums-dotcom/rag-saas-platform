"""Partie 10.4 -- GDPR/CCPA rights-request tracking, per-category
consent, and breach declaration, built on top of the already-mature
export/deletion machinery (api/services/data_export.py, DELETE
/account/me)."""

import pytest


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def test_create_and_list_data_request(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))

    create_response = await client.post("/compliance/data-requests", json={"request_type": "access", "details": "please send my data"}, headers=_auth_header(token))
    assert create_response.status_code == 201
    request_id = create_response.json()["id"]
    assert create_response.json()["status"] == "pending"

    get_response = await client.get(f"/compliance/data-requests/{request_id}", headers=_auth_header(token))
    assert get_response.status_code == 200

    user.role = UserRole.admin
    await db_session.commit()
    admin_list = await client.get("/compliance/data-requests", headers=_auth_header(token))
    assert admin_list.status_code == 200
    assert any(item["id"] == request_id for item in admin_list.json())


async def test_process_data_request_transitions_status(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    request_id = (await client.post("/compliance/data-requests", json={"request_type": "erasure"}, headers=_auth_header(token))).json()["id"]

    user.role = UserRole.admin
    await db_session.commit()
    process_response = await client.post(f"/compliance/data-requests/{request_id}/process", headers=_auth_header(token))
    assert process_response.status_code == 200
    assert process_response.json()["status"] == "in_progress"

    patch_response = await client.patch(f"/compliance/data-requests/{request_id}", json={"status": "completed", "resolution_note": "done"}, headers=_auth_header(token))
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "completed"
    assert patch_response.json()["processed_at"] is not None


async def test_consent_record_and_withdraw(client, db_session, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]

    await client.post("/compliance/consent", json={"consent_type": "marketing", "granted": True}, headers=_auth_header(token))
    listing = await client.get("/compliance/consent", headers=_auth_header(token))
    assert listing.status_code == 200
    assert any(c["consent_type"] == "marketing" and c["granted"] is True for c in listing.json())

    withdraw_response = await client.delete("/compliance/consent/marketing", headers=_auth_header(token))
    assert withdraw_response.status_code == 200
    assert withdraw_response.json()["granted"] is False

    listing_after = await client.get("/compliance/consent", headers=_auth_header(token))
    marketing_entry = next(c for c in listing_after.json() if c["consent_type"] == "marketing")
    assert marketing_entry["granted"] is False  # the LATEST row wins


async def test_data_export_reuses_existing_account_export(client, db_session, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.get("/compliance/data-export?fmt=json", headers=_auth_header(token))
    assert response.status_code == 200
    assert register_payload["email"] in response.text


async def test_compliance_status_requires_admin(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    non_admin_response = await client.get("/compliance/status", headers=_auth_header(token))
    assert non_admin_response.status_code == 404  # require_admin's anti-enumeration 404

    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.admin
    await db_session.commit()
    admin_response = await client.get("/compliance/status", headers=_auth_header(token))
    assert admin_response.status_code == 200
    assert admin_response.json()["gdpr_export_available"] is True


async def test_declare_data_breach_requires_superadmin_and_dispatches_notification(client, db_session, register_payload, monkeypatch):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))

    forbidden = await client.post("/compliance/data-breach", json={"description": "a real incident", "affected_user_count": 1}, headers=_auth_header(token))
    assert forbidden.status_code == 403

    user.role = UserRole.superadmin
    await db_session.commit()

    dispatched = {}

    def _fake_delay(breach_id):
        dispatched["breach_id"] = breach_id

    monkeypatch.setattr("api.tasks.compliance.send_data_breach_notifications.delay", _fake_delay)

    response = await client.post("/compliance/data-breach", json={"description": "a real incident", "affected_user_count": 1}, headers=_auth_header(token))
    assert response.status_code == 201
    assert response.json()["notified_at"] is None
    assert dispatched["breach_id"] == response.json()["id"]
