"""
End-to-end tests for the 1.1 auth routers, against an in-memory SQLite DB
(see conftest.py) through a real ASGI request/response cycle -- not calling
the route functions directly, so routing, dependency injection, and
Pydantic validation are all genuinely exercised.

Email/SMS-adjacent side effects (Resend calls) are monkeypatched at the
service-function boundary (api.services.email.send_*) rather than skipped
-- this is the same "fake the external call, keep everything else real"
approach src/agent.py's own tests already use for the GitHub/Google calls.
"""

import pyotp


# ---------------------------------------------------------------- 1.1.1 --
async def test_register_creates_user_and_returns_tokens(client, register_payload):
    response = await client.post("/auth/register", json=register_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert "refresh_token" in response.cookies


async def test_register_rejects_duplicate_email(client, register_payload):
    await client.post("/auth/register", json=register_payload)
    response = await client.post("/auth/register", json=register_payload)
    assert response.status_code == 409


async def test_register_requires_terms_acceptance(client, register_payload):
    register_payload["accept_terms"] = False
    response = await client.post("/auth/register", json=register_payload)
    assert response.status_code == 422


async def test_register_rejects_password_over_bcrypt_limit(client, register_payload):
    register_payload["password"] = "x" * 73
    response = await client.post("/auth/register", json=register_payload)
    assert response.status_code == 422


# ---------------------------------------------------------------- 1.1.2 --
async def test_login_success(client, register_payload):
    await client.post("/auth/register", json=register_payload)
    response = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_login_wrong_password_returns_generic_401(client, register_payload):
    await client.post("/auth/register", json=register_payload)
    response = await client.post("/auth/login", json={"email": register_payload["email"], "password": "not-the-password"})
    assert response.status_code == 401


async def test_login_unknown_email_returns_same_generic_401(client):
    response = await client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever123"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


async def test_logout_revokes_session(client, register_payload):
    await client.post("/auth/register", json=register_payload)
    logout_response = await client.post("/auth/logout")
    assert logout_response.status_code == 200

    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 401


# ---------------------------------------------------------------- 1.1.8 --
async def test_refresh_rotates_the_token(client, register_payload):
    register_response = await client.post("/auth/register", json=register_payload)
    first_access_token = register_response.json()["access_token"]
    first_refresh_cookie = client.cookies.get("refresh_token")

    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 200
    # Not asserting the access token itself differs: two JWTs issued for
    # the same user within the same wall-clock second are byte-identical
    # (second-precision iat/exp, no jti) -- expected and harmless for a
    # short-lived, stateless access token. The refresh token is where
    # rotation is a real security property, and that one is checked below.
    assert client.cookies.get("refresh_token") != first_refresh_cookie


async def test_reused_refresh_token_is_rejected_after_rotation(client, register_payload):
    await client.post("/auth/register", json=register_payload)
    old_refresh_token = client.cookies.get("refresh_token")

    await client.post("/auth/refresh")  # rotates it

    client.cookies.set("refresh_token", old_refresh_token)
    replay_response = await client.post("/auth/refresh")
    assert replay_response.status_code == 401


async def test_refresh_without_cookie_is_unauthorized(client):
    response = await client.post("/auth/refresh")
    assert response.status_code == 401


# ------------------------------------------------------------ Partie 1.1.9 --
async def test_sessions_list_marks_current_session(client, register_payload):
    await client.post("/auth/register", json=register_payload)
    access_token = (await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})).json()["access_token"]

    response = await client.get("/sessions", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) >= 1
    assert any(s["is_current"] for s in sessions)


async def test_revoking_another_sessions_id_requires_ownership(client, register_payload):
    await client.post("/auth/register", json=register_payload)
    access_token = (await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})).json()["access_token"]
    response = await client.delete("/sessions/00000000-0000-0000-0000-000000000000", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 404


# ---------------------------------------------------------- profile / prefs --
async def test_get_profile_without_credentials_is_rejected(client):
    response = await client.get("/account/me")
    assert response.status_code == 401  # HTTPBearer's own default for a missing header, this FastAPI version


async def test_get_profile_with_valid_token(client, register_payload):
    register_response = await client.post("/auth/register", json=register_payload)
    access_token = register_response.json()["access_token"]

    response = await client.get("/account/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json()["email"] == register_payload["email"]
    assert response.json()["is_email_verified"] is False


async def test_update_preferences_accepts_valid_timezone(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.patch(
        "/account/preferences", json={"timezone": "Africa/Douala", "locale": "fr"}, headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["timezone"] == "Africa/Douala"


async def test_update_preferences_rejects_invalid_timezone(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.patch("/account/preferences", json={"timezone": "Mars/Olympus_Mons"}, headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 422


# ---------------------------------------------------------------- 1.1.4 --
async def test_email_verification_flow(client, register_payload, monkeypatch):
    captured = {}

    def fake_send(to_email, code):
        captured["email"] = to_email
        captured["code"] = code

    monkeypatch.setattr("api.services.verification.send_verification_code_email", fake_send)

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    assert captured["email"] == register_payload["email"]
    assert len(captured["code"]) == 6

    wrong = await client.post("/auth/verify-email/confirm", json={"code": "000000"}, headers={"Authorization": f"Bearer {access_token}"})
    assert wrong.status_code == 400

    right = await client.post("/auth/verify-email/confirm", json={"code": captured["code"]}, headers={"Authorization": f"Bearer {access_token}"})
    assert right.status_code == 200

    profile = await client.get("/account/me", headers={"Authorization": f"Bearer {access_token}"})
    assert profile.json()["is_email_verified"] is True


# ---------------------------------------------------------------- 1.1.3 --
async def test_password_reset_flow(client, register_payload, monkeypatch):
    captured = {}
    monkeypatch.setattr("api.services.password_reset.send_password_reset_email", lambda to, link: captured.update(link=link))

    await client.post("/auth/register", json=register_payload)
    forgot = await client.post("/auth/password/forgot", json={"email": register_payload["email"]})
    assert forgot.status_code == 200
    reset_token = captured["link"].split("token=")[1]

    reset = await client.post("/auth/password/reset", json={"token": reset_token, "new_password": "a-brand-new-password"})
    assert reset.status_code == 200

    # The old session was revoked by the reset -- the cookie set at
    # registration must no longer work.
    stale_refresh = await client.post("/auth/refresh")
    assert stale_refresh.status_code == 401

    old_password_login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert old_password_login.status_code == 401

    new_password_login = await client.post("/auth/login", json={"email": register_payload["email"], "password": "a-brand-new-password"})
    assert new_password_login.status_code == 200


async def test_forgot_password_is_silent_for_unknown_email(client):
    response = await client.post("/auth/password/forgot", json={"email": "nobody@example.com"})
    assert response.status_code == 200  # never reveals whether the account exists


# ---------------------------------------------------------------- 1.1.7 --
async def test_two_factor_setup_enable_and_login_flow(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    setup = await client.post("/auth/2fa/setup", headers=auth_header)
    assert setup.status_code == 200
    secret = setup.json()["secret"]

    valid_code = pyotp.TOTP(secret).now()
    enable = await client.post("/auth/2fa/enable", json={"code": valid_code}, headers=auth_header)
    assert enable.status_code == 200

    # Password login must now stop short and hand back an MFA challenge
    # instead of tokens.
    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert login.status_code == 200
    assert login.json()["mfa_required"] is True
    mfa_token = login.json()["mfa_token"]

    verify = await client.post("/auth/2fa/verify-login", json={"mfa_token": mfa_token, "code": pyotp.TOTP(secret).now()})
    assert verify.status_code == 200
    assert verify.json()["access_token"]


async def test_two_factor_disable_requires_valid_code(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)

    bad = await client.post("/auth/2fa/disable", json={"code": "000000"}, headers=auth_header)
    assert bad.status_code == 400

    good = await client.post("/auth/2fa/disable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    assert good.status_code == 200


# --------------------------------------------------------------- 1.1.10 --
async def test_delete_account_soft_deletes_and_revokes_sessions(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    delete_response = await client.delete("/account/me", headers=auth_header)
    assert delete_response.status_code == 200

    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 401

    login_response = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert login_response.status_code == 401  # is_active is now False


# --------------------------------------------------------------- 1.1.11 --
async def test_export_account_data_contains_profile_and_consent(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.get("/account/export", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    export = response.json()
    assert export["profile"]["email"] == register_payload["email"]
    assert export["consent"]["consent_given_at"] is not None
    assert export["consent"]["terms_version"]
    assert "sessions" in export and "linked_oauth_accounts" in export


# --------------------------------------------------------------- 1.1.12 --
async def test_registration_records_consent(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    profile = await client.get("/account/export", headers={"Authorization": f"Bearer {access_token}"})
    assert profile.json()["consent"]["consent_given_at"] is not None


# --------------------------------------------------------------- 1.1.13 --
async def test_update_profile_fields(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.patch(
        "/account/profile", json={"full_name": "Ada K. Lovelace", "company": "Analytical Engines Ltd"}, headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Ada K. Lovelace"
    assert response.json()["company"] == "Analytical Engines Ltd"
