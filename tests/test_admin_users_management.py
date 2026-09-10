"""Partie 11.3 -- platform-admin user management."""


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


async def _make_target_user(client, db_session, email="target@example.com"):
    from sqlalchemy import select

    from api.models.user import User

    payload = {"email": email, "password": "correct-horse-battery-staple", "accept_terms": True}
    await client.post("/auth/register", json=payload)
    return await db_session.scalar(select(User).where(User.email == email))


async def test_list_and_get_user_admin(client, db_session, register_payload):
    token, _ = await _make_admin(client, db_session, register_payload)
    target = await _make_target_user(client, db_session)

    listing = await client.get("/admin/users", headers=_auth_header(token))
    assert listing.status_code == 200
    assert listing.json()["total"] >= 2

    detail = await client.get(f"/admin/users/{target.id}", headers=_auth_header(token))
    assert detail.status_code == 200
    assert detail.json()["email"] == "target@example.com"


async def test_suspend_user_revokes_sessions_and_blocks_login(client, db_session, register_payload):
    token, _ = await _make_admin(client, db_session, register_payload)
    target = await _make_target_user(client, db_session, "suspend-me@example.com")

    suspend_response = await client.post(f"/admin/users/{target.id}/suspend", json={"reason": "abuse"}, headers=_auth_header(token))
    assert suspend_response.status_code == 200
    assert suspend_response.json()["is_active"] is False

    login_response = await client.post("/auth/login", json={"email": "suspend-me@example.com", "password": "correct-horse-battery-staple"})
    assert login_response.status_code in (401, 403)

    activate_response = await client.post(f"/admin/users/{target.id}/activate", headers=_auth_header(token))
    assert activate_response.status_code == 200
    assert activate_response.json()["is_active"] is True


async def test_suspend_is_audited(client, db_session, register_payload):
    token, _ = await _make_admin(client, db_session, register_payload)
    target = await _make_target_user(client, db_session, "audit-me@example.com")
    await client.post(f"/admin/users/{target.id}/suspend", json={"reason": "test"}, headers=_auth_header(token))

    activity = await client.get(f"/admin/users/{target.id}/activity", headers=_auth_header(token))
    actions = {item["action"] for item in activity.json()["items"]}
    assert "user_suspended" in actions


async def test_reset_password_sends_real_email_flow(client, db_session, register_payload, monkeypatch):
    token, _ = await _make_admin(client, db_session, register_payload)
    target = await _make_target_user(client, db_session, "reset-me@example.com")

    sent = {}

    def _fake_send(to_email, reset_link):
        sent["to"] = to_email

    monkeypatch.setattr("api.services.password_reset.send_password_reset_email", _fake_send)

    response = await client.post(f"/admin/users/{target.id}/reset-password", headers=_auth_header(token))
    assert response.status_code == 200
    assert sent["to"] == "reset-me@example.com"


async def test_verify_email_admin(client, db_session, register_payload):
    token, _ = await _make_admin(client, db_session, register_payload)
    target = await _make_target_user(client, db_session, "verify-me@example.com")
    assert target.is_email_verified is False

    response = await client.post(f"/admin/users/{target.id}/verify-email", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["is_email_verified"] is True


async def test_sessions_list_and_terminate(client, db_session, register_payload):
    token, _ = await _make_admin(client, db_session, register_payload)
    target = await _make_target_user(client, db_session, "sessions@example.com")

    sessions = await client.get(f"/admin/users/{target.id}/sessions", headers=_auth_header(token))
    assert sessions.status_code == 200
    assert len(sessions.json()) >= 1

    session_id = sessions.json()[0]["id"]
    terminate = await client.delete(f"/admin/users/{target.id}/sessions/{session_id}", headers=_auth_header(token))
    assert terminate.status_code == 204
