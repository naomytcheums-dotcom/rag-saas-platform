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

import datetime as dt

import jwt as pyjwt
import pyotp
from sqlalchemy import select

from api.config import settings
from api.models.revoked_token import RevokedAccessToken
from api.models.user import User


def _csrf(client):
    """POST /auth/refresh and /auth/logout are CSRF-protected (1.1.16,
    api/security/csrf.py's double-submit check) -- the caller must echo
    back whatever csrf_token cookie the client currently holds (set
    alongside the refresh cookie by every issue_session() call) as an
    X-CSRF-Token header. A real browser's JS does this automatically;
    tests do it explicitly, here."""
    return {"X-CSRF-Token": client.cookies.get("csrf_token") or ""}


def _jti_of(access_token):
    """Pulls the jti claim straight out of a JWT without verifying its
    signature -- fine for a test that already trusts this token was
    legitimately issued moments ago by the very server under test, and
    lets these tests check the 1.1.15 blacklist directly (was a
    RevokedAccessToken row actually written for THIS jti?) instead of
    only inferring it indirectly through an HTTP 401 that could just as
    easily come from is_active being False."""
    return pyjwt.decode(access_token, options={"verify_signature": False})["jti"]


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
    refresh_cookie_before_logout = client.cookies.get("refresh_token")
    csrf_cookie_before_logout = client.cookies.get("csrf_token")

    logout_response = await client.post("/auth/logout", headers=_csrf(client))
    assert logout_response.status_code == 200

    # logout() clears both cookies for the current client, so a plain
    # refresh call now hits the CSRF gate first, not the session check --
    # a real browser in this state has neither cookie left to send either.
    refresh_response = await client.post("/auth/refresh", headers=_csrf(client))
    assert refresh_response.status_code == 403
    assert client.cookies.get("refresh_token") is None
    assert client.cookies.get("csrf_token") is None

    # The session itself was genuinely revoked server-side, not just
    # unreachable through the now-cleared cookies: replaying the exact
    # (still self-consistent) cookie pair captured before logout passes
    # CSRF but correctly fails on the actual, revoked session.
    client.cookies.set("refresh_token", refresh_cookie_before_logout)
    client.cookies.set("csrf_token", csrf_cookie_before_logout)
    replay_response = await client.post("/auth/refresh", headers={"X-CSRF-Token": csrf_cookie_before_logout})
    assert replay_response.status_code == 401


async def test_logout_blacklists_the_access_token_even_if_it_hasnt_expired(client, register_payload):
    """1.1.15: logout must kill BOTH halves of the session, not just the
    refresh cookie -- the access token issued at login/register must stop
    working immediately too, not linger for its remaining ~15 minutes."""
    register_response = await client.post("/auth/register", json=register_payload)
    access_token = register_response.json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    still_valid = await client.get("/account/me", headers=auth_header)
    assert still_valid.status_code == 200

    await client.post("/auth/logout", headers=_csrf(client))

    now_blacklisted = await client.get("/account/me", headers=auth_header)
    assert now_blacklisted.status_code == 401


async def test_blacklist_still_applies_to_a_token_verified_via_a_previous_jwt_key(client, register_payload, monkeypatch):
    """1.1.15's two mechanisms (key rotation and the blacklist) are
    independent by construction -- the blacklist check runs after
    decode_token() succeeds, regardless of which configured key actually
    verified the signature. Proven directly rather than assumed: a token
    signed under an OLD key, now listed in JWT_PREVIOUS_SECRET_KEYS,
    must still be rejected once its jti is blacklisted -- key rotation
    is not a way to slip past a revocation.
    """
    old_key = "old-signing-key-for-this-test-" + "x" * 20
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", old_key)

    register_response = await client.post("/auth/register", json=register_payload)
    access_token_signed_with_old_key = register_response.json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token_signed_with_old_key}"}

    # Rotate: a new current key, the old one demoted to "still verifiable."
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "new-signing-key-for-this-test-" + "y" * 20)
    monkeypatch.setattr(settings, "JWT_PREVIOUS_SECRET_KEYS", old_key)

    # The old-key token still works post-rotation -- the whole point of
    # JWT_PREVIOUS_SECRET_KEYS.
    still_valid_after_rotation = await client.get("/account/me", headers=auth_header)
    assert still_valid_after_rotation.status_code == 200

    # Now blacklist it (logout doesn't re-decode the JWT at all -- it
    # reads the jti straight off the Session row -- so this works
    # regardless of which key originally signed the token).
    await client.post("/auth/logout", headers=_csrf(client))

    # Still verifies fine under the previous key -- but now correctly
    # rejected anyway, because the blacklist check is independent of
    # signature verification.
    now_blacklisted_despite_valid_old_key_signature = await client.get("/account/me", headers=auth_header)
    assert now_blacklisted_despite_valid_old_key_signature.status_code == 401


# ---------------------------------------------------------------- 1.1.8 --
async def test_refresh_rotates_the_token(client, register_payload):
    register_response = await client.post("/auth/register", json=register_payload)
    first_access_token = register_response.json()["access_token"]
    first_refresh_cookie = client.cookies.get("refresh_token")

    refresh_response = await client.post("/auth/refresh", headers=_csrf(client))
    assert refresh_response.status_code == 200
    # Every token now carries a unique jti (1.1.15), so two tokens for
    # the same user are never byte-identical even issued in the same
    # wall-clock second -- a real, meaningful difference now, not just
    # "different enough not to assert on."
    assert refresh_response.json()["access_token"] != first_access_token
    assert client.cookies.get("refresh_token") != first_refresh_cookie


async def test_refresh_blacklists_the_old_access_token(client, register_payload):
    """A bonus consequence of 1.1.15's design, not just tested for its
    own sake: since revoke_session() (called on the OLD session as part
    of refresh rotation) now blacklists that session's access token too,
    the pre-refresh access token dies immediately instead of surviving
    for its own remaining ~15 minutes after a refresh."""
    register_response = await client.post("/auth/register", json=register_payload)
    old_access_token = register_response.json()["access_token"]

    await client.post("/auth/refresh", headers=_csrf(client))

    response = await client.get("/account/me", headers={"Authorization": f"Bearer {old_access_token}"})
    assert response.status_code == 401


async def test_reused_refresh_token_is_rejected_after_rotation(client, register_payload):
    await client.post("/auth/register", json=register_payload)
    old_refresh_token = client.cookies.get("refresh_token")

    await client.post("/auth/refresh", headers=_csrf(client))  # rotates it

    client.cookies.set("refresh_token", old_refresh_token)
    replay_response = await client.post("/auth/refresh", headers=_csrf(client))
    assert replay_response.status_code == 401


async def test_refresh_without_any_cookies_is_rejected_by_csrf_first(client):
    """No prior session at all (never logged in) means no csrf_token
    cookie either -- the CSRF gate (1.1.16) rejects this before the
    route body ever runs, which is correct: there is nothing for
    /auth/refresh to do for a caller that was never issued a session."""
    response = await client.post("/auth/refresh")
    assert response.status_code == 403


async def test_refresh_with_valid_csrf_but_no_refresh_cookie_is_unauthorized(client, register_payload):
    """Isolates the scenario the CSRF-less version of this test used to
    check: a caller that HAS a valid session (so CSRF passes) but whose
    refresh_token cookie is missing/was cleared must still be rejected,
    just for the actual reason (no refresh token), not a CSRF failure."""
    await client.post("/auth/register", json=register_payload)
    headers = _csrf(client)
    client.cookies.delete("refresh_token")

    response = await client.post("/auth/refresh", headers=headers)
    assert response.status_code == 401


async def test_refresh_rejects_a_csrf_header_that_does_not_match_the_cookie(client, register_payload):
    """The core double-submit property (1.1.16): having A valid-looking
    csrf_token cookie is not enough -- the header must match THAT exact
    cookie. A cross-site attacker's page can make the cookie get sent
    automatically but can't read its value to forge a matching header."""
    await client.post("/auth/register", json=register_payload)
    response = await client.post("/auth/refresh", headers={"X-CSRF-Token": "attacker-guessed-wrong-value"})
    assert response.status_code == 403


async def test_logout_rejects_a_missing_csrf_header(client, register_payload):
    await client.post("/auth/register", json=register_payload)
    response = await client.post("/auth/logout")  # no X-CSRF-Token header at all
    assert response.status_code == 403


async def test_logout_rejects_a_csrf_header_that_does_not_match_the_cookie(client, register_payload):
    await client.post("/auth/register", json=register_payload)
    response = await client.post("/auth/logout", headers={"X-CSRF-Token": "attacker-guessed-wrong-value"})
    assert response.status_code == 403


async def test_new_login_notification_fires_on_ip_change_even_with_the_same_device(client, register_payload, monkeypatch):
    """issue_session()'s "new device" check requires BOTH the User-Agent
    AND the IP to match a prior session, not just the User-Agent -- a
    stolen refresh token replayed from a different network must still
    look "new" even if the attacker's client sends the exact same
    User-Agent string. Register (no notification -- see auth.py's
    register()) then log in twice: once from the registration's own
    default IP (recognized, no email), once from a different IP with the
    identical User-Agent (must still count as new)."""
    sent = []
    monkeypatch.setattr(
        "api.security.sessions.send_new_login_notification_email",
        lambda to, device, ip, when: sent.append(ip),
    )

    await client.post("/auth/register", json=register_payload)

    same_ip_login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert same_ip_login.status_code == 200
    assert sent == []  # same device_info AND same (default) IP as registration -- recognized

    new_ip_login = await client.post(
        "/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
        headers={"X-Forwarded-For": "203.0.113.77"},  # same User-Agent, different IP
    )
    assert new_ip_login.status_code == 200
    assert sent == ["203.0.113.77"]  # flagged as new despite the matching User-Agent


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


async def test_revoking_a_specific_session_blacklists_only_its_own_access_token(client, register_payload):
    """1.1.15's "suspicious session" scenario: revoking one device by id
    (e.g. one the user doesn't recognize in their session list) must
    kill THAT session's access token immediately, without touching any
    OTHER session's still-legitimate access token -- registering, then
    logging in again, gives two distinct sessions/access tokens for the
    same account to tell apart."""
    register = await client.post("/auth/register", json=register_payload)
    access_token_a = register.json()["access_token"]

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    access_token_b = login.json()["access_token"]
    auth_header_b = {"Authorization": f"Bearer {access_token_b}"}

    sessions = (await client.get("/sessions", headers=auth_header_b)).json()
    session_a_id = next(s["id"] for s in sessions if not s["is_current"])

    revoke = await client.delete(f"/sessions/{session_a_id}", headers=auth_header_b)
    assert revoke.status_code == 200

    session_a_now_dead = await client.get("/account/me", headers={"Authorization": f"Bearer {access_token_a}"})
    assert session_a_now_dead.status_code == 401

    session_b_still_alive = await client.get("/account/me", headers=auth_header_b)
    assert session_b_still_alive.status_code == 200


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


async def test_email_otp_cannot_be_reused_after_success(client, register_payload, monkeypatch):
    captured = {}
    monkeypatch.setattr("api.services.verification.send_verification_code_email", lambda to, code: captured.update(code=code))

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    first = await client.post("/auth/verify-email/confirm", json={"code": captured["code"]}, headers=auth_header)
    assert first.status_code == 200

    replay = await client.post("/auth/verify-email/confirm", json={"code": captured["code"]}, headers=auth_header)
    assert replay.status_code == 400  # the token was marked used_at, so no unused row matches anymore


async def test_email_otp_expired_code_is_rejected(client, register_payload, monkeypatch, db_session):
    import datetime as dt
    from sqlalchemy import select
    from api.models.token import EmailVerificationToken

    captured = {}
    monkeypatch.setattr("api.services.verification.send_verification_code_email", lambda to, code: captured.update(code=code))

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]

    token_row = await db_session.scalar(select(EmailVerificationToken))
    token_row.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    await db_session.commit()

    response = await client.post("/auth/verify-email/confirm", json={"code": captured["code"]}, headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 400


async def test_email_otp_max_attempts_exceeded(client, register_payload, monkeypatch):
    monkeypatch.setattr("api.services.verification.send_verification_code_email", lambda to, code: None)
    monkeypatch.setattr("api.config.settings.EMAIL_OTP_MAX_ATTEMPTS", 3)

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    for _ in range(3):
        r = await client.post("/auth/verify-email/confirm", json={"code": "000000"}, headers=auth_header)
        assert r.status_code == 400

    locked_out = await client.post("/auth/verify-email/confirm", json={"code": "000000"}, headers=auth_header)
    assert locked_out.status_code == 429


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
    stale_refresh = await client.post("/auth/refresh", headers=_csrf(client))
    assert stale_refresh.status_code == 401

    old_password_login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert old_password_login.status_code == 401

    new_password_login = await client.post("/auth/login", json={"email": register_payload["email"], "password": "a-brand-new-password"})
    assert new_password_login.status_code == 200


async def test_password_reset_blacklists_the_access_token_issued_before_it(client, register_payload, monkeypatch):
    """1.1.15's actual validation criterion: a token stolen BEFORE a
    password reset must not still work AFTER it, for its own remaining
    ~15 minutes. The stale-refresh-token check above proves the session
    row is gone; this proves the access token specifically -- a
    self-contained JWT that doesn't even touch the Session table -- is
    also rejected, via the blacklist, not just "would have expired
    eventually."

    Two distinct sessions (registration + a second login from a
    different "device") on purpose: revoke_all_sessions_for_user() loops
    over every active session, and that loop must genuinely blacklist
    ALL of them, not just happen to work for the trivial one-session
    case."""
    captured = {}
    monkeypatch.setattr("api.services.password_reset.send_password_reset_email", lambda to, link: captured.update(link=link))

    register = await client.post("/auth/register", json=register_payload)
    access_token_a = register.json()["access_token"]
    auth_header_a = {"Authorization": f"Bearer {access_token_a}"}

    login = await client.post(
        "/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]},
        headers={"User-Agent": "a-second-device/1.0"},
    )
    access_token_b = login.json()["access_token"]
    auth_header_b = {"Authorization": f"Bearer {access_token_b}"}

    assert (await client.get("/account/me", headers=auth_header_a)).status_code == 200
    assert (await client.get("/account/me", headers=auth_header_b)).status_code == 200

    await client.post("/auth/password/forgot", json={"email": register_payload["email"]})
    reset_token = captured["link"].split("token=")[1]
    await client.post("/auth/password/reset", json={"token": reset_token, "new_password": "a-brand-new-password"})

    assert (await client.get("/account/me", headers=auth_header_a)).status_code == 401
    assert (await client.get("/account/me", headers=auth_header_b)).status_code == 401


async def test_forgot_password_is_silent_for_unknown_email(client):
    response = await client.post("/auth/password/forgot", json={"email": "nobody@example.com"})
    assert response.status_code == 200  # never reveals whether the account exists


async def test_password_reset_token_cannot_be_reused(client, register_payload, monkeypatch):
    captured = {}
    monkeypatch.setattr("api.services.password_reset.send_password_reset_email", lambda to, link: captured.update(link=link))

    await client.post("/auth/register", json=register_payload)
    await client.post("/auth/password/forgot", json={"email": register_payload["email"]})
    reset_token = captured["link"].split("token=")[1]

    first = await client.post("/auth/password/reset", json={"token": reset_token, "new_password": "first-new-password"})
    assert first.status_code == 200

    replay = await client.post("/auth/password/reset", json={"token": reset_token, "new_password": "second-new-password"})
    assert replay.status_code == 400  # used_at is set after the first reset


async def test_password_reset_expired_token_is_rejected(client, register_payload, monkeypatch, db_session):
    import datetime as dt
    from sqlalchemy import select
    from api.models.token import PasswordResetToken

    captured = {}
    monkeypatch.setattr("api.services.password_reset.send_password_reset_email", lambda to, link: captured.update(link=link))

    await client.post("/auth/register", json=register_payload)
    await client.post("/auth/password/forgot", json={"email": register_payload["email"]})
    reset_token = captured["link"].split("token=")[1]

    token_row = await db_session.scalar(select(PasswordResetToken))
    token_row.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    await db_session.commit()

    response = await client.post("/auth/password/reset", json={"token": reset_token, "new_password": "a-new-password"})
    assert response.status_code == 400


async def test_password_reset_garbage_token_is_rejected(client):
    response = await client.post("/auth/password/reset", json={"token": "this-was-never-issued", "new_password": "a-new-password"})
    assert response.status_code == 400


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


async def test_a_session_issued_via_2fa_verify_login_is_genuinely_blacklistable(client, register_payload):
    """1.1.15, proven directly rather than assumed from 'it's the same
    issue_session() call every other login path uses': the access token
    issued by /2fa/verify-login must be revocable through the normal
    session-revoke path (DELETE /sessions/{id}), exactly like a token
    from a plain password login."""
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]
    verify = await client.post("/auth/2fa/verify-login", json={"mfa_token": mfa_token, "code": pyotp.TOTP(secret).now()})
    two_fa_access_token = verify.json()["access_token"]
    two_fa_auth_header = {"Authorization": f"Bearer {two_fa_access_token}"}

    still_valid = await client.get("/account/me", headers=two_fa_auth_header)
    assert still_valid.status_code == 200

    current_session_id = next(s["id"] for s in (await client.get("/sessions", headers=two_fa_auth_header)).json() if s["is_current"])
    revoke = await client.delete(f"/sessions/{current_session_id}", headers=two_fa_auth_header)
    assert revoke.status_code == 200

    now_blacklisted = await client.get("/account/me", headers=two_fa_auth_header)
    assert now_blacklisted.status_code == 401


async def test_two_factor_disable_requires_valid_code(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)

    bad = await client.post("/auth/2fa/disable", json={"code": "000000"}, headers=auth_header)
    assert bad.status_code == 400

    good = await client.post("/auth/2fa/disable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    assert good.status_code == 200


async def test_disabling_two_factor_sends_a_notification_email(client, register_payload, monkeypatch):
    captured = []
    monkeypatch.setattr("api.routers.two_factor.send_two_factor_disabled_email", lambda to: captured.append(to))

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)

    await client.post("/auth/2fa/disable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    assert captured == [register_payload["email"]]


async def test_two_factor_enable_returns_ten_unique_recovery_codes(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]

    enable = await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    assert enable.status_code == 200
    codes = enable.json()["recovery_codes"]
    assert len(codes) == 10
    assert len(set(codes)) == 10  # no duplicates in one batch


async def test_recovery_codes_file_is_a_downloadable_text_file_with_the_same_codes(client, register_payload):
    import base64

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]

    enable = await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    body = enable.json()
    codes_file = body["recovery_codes_file"]
    assert codes_file.startswith("data:text/plain;charset=utf-8;base64,")

    encoded = codes_file.split(",", 1)[1]
    decoded_text = base64.b64decode(encoded).decode("utf-8")
    for code in body["recovery_codes"]:
        assert code in decoded_text  # every code the JSON list has is really in the downloadable file too


async def test_enabling_two_factor_sends_a_notification_email(client, register_payload, monkeypatch):
    """The real risk this closes: /setup hands back the TOTP secret in
    plaintext to anyone holding a valid access token, and /enable only
    needs a code derived from it -- an attacker with a stolen token
    could scan that QR code into their OWN authenticator and enable 2FA
    under a secret only they control, locking the real owner out before
    anything else looks wrong. This email is the one signal that would
    catch it in time."""
    captured = []
    monkeypatch.setattr("api.routers.two_factor.send_two_factor_enabled_email", lambda to: captured.append(to))

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]

    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    assert captured == [register_payload["email"]]


async def test_recovery_code_logs_in_and_cannot_be_reused(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    enable = await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    recovery_code = enable.json()["recovery_codes"][0]

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]

    # Works with the dashes exactly as issued...
    first_use = await client.post("/auth/2fa/verify-recovery-code", json={"mfa_token": mfa_token, "recovery_code": recovery_code})
    assert first_use.status_code == 200
    assert first_use.json()["access_token"]

    # ...but the same code is now dead, even against a brand new login attempt.
    login2 = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token2 = login2.json()["mfa_token"]
    second_use = await client.post("/auth/2fa/verify-recovery-code", json={"mfa_token": mfa_token2, "recovery_code": recovery_code})
    assert second_use.status_code == 401


async def test_a_session_issued_via_2fa_verify_recovery_code_is_genuinely_blacklistable(client, register_payload):
    """1.1.15, same exhaustiveness reasoning as the /verify-login version
    of this test: every distinct issue_session() call site in this app
    (register, login, refresh, the OAuth callback, /verify-login,
    /verify-recovery-code) is proven individually blacklistable, not
    assumed from the others because they share the same function."""
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    enable = await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    recovery_code = enable.json()["recovery_codes"][0]

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]
    verify = await client.post("/auth/2fa/verify-recovery-code", json={"mfa_token": mfa_token, "recovery_code": recovery_code})
    recovery_access_token = verify.json()["access_token"]
    recovery_auth_header = {"Authorization": f"Bearer {recovery_access_token}"}

    still_valid = await client.get("/account/me", headers=recovery_auth_header)
    assert still_valid.status_code == 200

    await client.post("/auth/logout", headers=_csrf(client))

    now_blacklisted = await client.get("/account/me", headers=recovery_auth_header)
    assert now_blacklisted.status_code == 401


async def test_recovery_code_is_case_and_dash_insensitive(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    enable = await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    recovery_code = enable.json()["recovery_codes"][0]
    messy = recovery_code.lower().replace("-", " ")  # e.g. "7k9p qx3m 2vyt"

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]

    verify = await client.post("/auth/2fa/verify-recovery-code", json={"mfa_token": mfa_token, "recovery_code": messy})
    assert verify.status_code == 200


async def test_disabling_two_factor_invalidates_leftover_recovery_codes(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    enable = await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    recovery_code = enable.json()["recovery_codes"][0]

    await client.post("/auth/2fa/disable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)

    # Re-enable with a fresh secret/QR -- the old recovery code must not
    # have survived the disable, even though the account has 2FA again.
    secret2 = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret2).now()}, headers=auth_header)

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]
    verify = await client.post("/auth/2fa/verify-recovery-code", json={"mfa_token": mfa_token, "recovery_code": recovery_code})
    assert verify.status_code == 401


async def test_regenerate_recovery_codes_requires_valid_totp_and_invalidates_old_batch(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    enable = await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    old_code = enable.json()["recovery_codes"][0]

    bad = await client.post("/auth/2fa/recovery-codes/regenerate", json={"code": "000000"}, headers=auth_header)
    assert bad.status_code == 400

    regenerate = await client.post("/auth/2fa/recovery-codes/regenerate", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    assert regenerate.status_code == 200
    new_codes = regenerate.json()["recovery_codes"]
    assert len(new_codes) == 10
    assert old_code not in new_codes
    assert regenerate.json()["recovery_codes_file"].startswith("data:text/plain;charset=utf-8;base64,")

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]

    old_still_dead = await client.post("/auth/2fa/verify-recovery-code", json={"mfa_token": mfa_token, "recovery_code": old_code})
    assert old_still_dead.status_code == 401

    new_works = await client.post("/auth/2fa/verify-recovery-code", json={"mfa_token": mfa_token, "recovery_code": new_codes[1]})
    assert new_works.status_code == 200


async def test_regenerating_recovery_codes_sends_a_notification_email(client, register_payload, monkeypatch):
    captured = []
    monkeypatch.setattr("api.routers.two_factor.send_recovery_codes_regenerated_email", lambda to: captured.append(to))

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)

    await client.post("/auth/2fa/recovery-codes/regenerate", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    assert captured == [register_payload["email"]]


async def test_unknown_recovery_code_is_rejected(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]

    verify = await client.post("/auth/2fa/verify-recovery-code", json={"mfa_token": mfa_token, "recovery_code": "AAAA-AAAA-AAAA"})
    assert verify.status_code == 401


async def test_recovery_codes_status_is_zero_when_2fa_is_not_enabled(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    status_response = await client.get("/auth/2fa/recovery-codes/status", headers=auth_header)
    assert status_response.status_code == 200
    assert status_response.json() == {"total": 0, "remaining": 0}


async def test_recovery_codes_status_decrements_as_codes_are_used(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    enable = await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    codes = enable.json()["recovery_codes"]

    fresh = await client.get("/auth/2fa/recovery-codes/status", headers=auth_header)
    assert fresh.json() == {"total": 10, "remaining": 10}

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]
    await client.post("/auth/2fa/verify-recovery-code", json={"mfa_token": mfa_token, "recovery_code": codes[0]})

    after_use = await client.get("/auth/2fa/recovery-codes/status", headers=auth_header)
    assert after_use.json() == {"total": 10, "remaining": 9}


async def test_lockout_recovery_disables_2fa_after_the_delay_elapses(client, register_payload, monkeypatch, db_session):
    import datetime as dt

    from api.models.lockout_recovery_token import TwoFactorLockoutRecoveryToken

    captured = {}
    monkeypatch.setattr(
        "api.services.two_factor_lockout_recovery.send_two_factor_lockout_recovery_requested_email",
        lambda to, link, delay_hours: captured.update(link=link),
    )

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)

    request = await client.post("/auth/2fa/lockout-recovery/request", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert request.status_code == 200
    token = captured["link"].split("token=")[1]

    # Too early -- the mandatory delay hasn't passed yet.
    too_early = await client.post("/auth/2fa/lockout-recovery/confirm", json={"token": token})
    assert too_early.status_code == 400

    # Simulate the delay having elapsed (real time can't be fast-forwarded in a test).
    row = await db_session.scalar(select(TwoFactorLockoutRecoveryToken))
    row.created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=settings.TWO_FA_LOCKOUT_RECOVERY_DELAY_HOURS, minutes=1)
    await db_session.commit()

    confirm = await client.post("/auth/2fa/lockout-recovery/confirm", json={"token": token})
    assert confirm.status_code == 200

    # 2FA is off entirely -- a plain password login now succeeds directly.
    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert login.status_code == 200
    assert login.json().get("access_token")

    # 1.1.15: unlike delete_account/withdraw_consent, this flow never
    # touches is_active -- the access token issued at registration dying
    # here is proof the blacklist itself (revoke_all_sessions_for_user)
    # is what's doing the work, not a side effect of some other check.
    old_access_token_now_dead = await client.get("/account/me", headers=auth_header)
    assert old_access_token_now_dead.status_code == 401


async def test_lockout_recovery_request_is_silent_for_wrong_password(client, register_payload, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "api.services.two_factor_lockout_recovery.send_two_factor_lockout_recovery_requested_email",
        lambda to, link, delay_hours: captured.update(link=link),
    )
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)

    response = await client.post("/auth/2fa/lockout-recovery/request", json={"email": register_payload["email"], "password": "totally-wrong-password"})
    assert response.status_code == 200  # same generic message regardless
    assert "link" not in captured  # ...but nothing was actually sent


async def test_lockout_recovery_request_is_silent_when_2fa_is_not_enabled(client, register_payload, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "api.services.two_factor_lockout_recovery.send_two_factor_lockout_recovery_requested_email",
        lambda to, link, delay_hours: captured.update(link=link),
    )
    await client.post("/auth/register", json=register_payload)  # 2FA never enabled

    response = await client.post("/auth/2fa/lockout-recovery/request", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert response.status_code == 200
    assert "link" not in captured


async def test_a_normal_2fa_login_cancels_a_pending_lockout_recovery_request(client, register_payload, monkeypatch, db_session):
    """The real owner logging in normally -- proving they still control
    2FA -- must invalidate a lockout-recovery request an attacker (who'd
    only have the password) is relying on instead. Without this, a
    stolen password alone could still wipe 2FA hours later even though
    the legitimate owner never lost access to anything."""
    import datetime as dt

    from api.models.lockout_recovery_token import TwoFactorLockoutRecoveryToken

    captured = {}
    monkeypatch.setattr(
        "api.services.two_factor_lockout_recovery.send_two_factor_lockout_recovery_requested_email",
        lambda to, link, delay_hours: captured.update(link=link),
    )

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)

    # Attacker (or anyone) requests lockout recovery with the correct password.
    await client.post("/auth/2fa/lockout-recovery/request", json={"email": register_payload["email"], "password": register_payload["password"]})
    token = captured["link"].split("token=")[1]

    # The real owner logs in normally with their authenticator in the meantime.
    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]
    verify = await client.post("/auth/2fa/verify-login", json={"mfa_token": mfa_token, "code": pyotp.TOTP(secret).now()})
    assert verify.status_code == 200

    # Fast-forward past the delay and try to confirm the (now-cancelled) token.
    row = await db_session.scalar(select(TwoFactorLockoutRecoveryToken))
    assert row is None  # the normal login above already deleted it

    confirm = await client.post("/auth/2fa/lockout-recovery/confirm", json={"token": token})
    assert confirm.status_code == 400


async def test_lockout_recovery_token_cannot_be_reused(client, register_payload, monkeypatch, db_session):
    import datetime as dt

    from api.models.lockout_recovery_token import TwoFactorLockoutRecoveryToken

    captured = {}
    monkeypatch.setattr(
        "api.services.two_factor_lockout_recovery.send_two_factor_lockout_recovery_requested_email",
        lambda to, link, delay_hours: captured.update(link=link),
    )
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    await client.post("/auth/2fa/lockout-recovery/request", json={"email": register_payload["email"], "password": register_payload["password"]})
    token = captured["link"].split("token=")[1]

    row = await db_session.scalar(select(TwoFactorLockoutRecoveryToken))
    row.created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=settings.TWO_FA_LOCKOUT_RECOVERY_DELAY_HOURS, minutes=1)
    await db_session.commit()

    first = await client.post("/auth/2fa/lockout-recovery/confirm", json={"token": token})
    assert first.status_code == 200

    replay = await client.post("/auth/2fa/lockout-recovery/confirm", json={"token": token})
    assert replay.status_code == 400


async def test_lockout_recovery_garbage_token_is_rejected(client):
    response = await client.post("/auth/2fa/lockout-recovery/confirm", json={"token": "this-was-never-issued"})
    assert response.status_code == 400


# --------------------------------------------------------------- 1.1.10 --
async def test_delete_account_soft_deletes_and_revokes_sessions(client, register_payload, db_session):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    delete_response = await client.delete("/account/me", headers=auth_header)
    assert delete_response.status_code == 200

    # 1.1.15: the blacklist row itself was written -- checked directly,
    # not just inferred from the 401 below, since is_active turning False
    # would produce that same 401 even if revoke_all_sessions_for_user's
    # blacklist half were silently broken.
    blacklisted = await db_session.scalar(select(RevokedAccessToken).where(RevokedAccessToken.jti == _jti_of(access_token)))
    assert blacklisted is not None

    refresh_response = await client.post("/auth/refresh", headers=_csrf(client))
    assert refresh_response.status_code == 401

    login_response = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert login_response.status_code == 401  # is_active is now False


async def test_delete_account_sends_an_immediate_deletion_scheduled_email(client, register_payload, monkeypatch):
    """4.6, half one of two: the FIRST of two warnings before permanent
    deletion -- an immediate confirmation the moment deletion is
    requested, distinct from the closer-to-the-deadline reminder the
    Celery task (api/tasks/account_deletion_reminder.py) sends later."""
    captured = []
    monkeypatch.setattr(
        "api.routers.account.send_account_deletion_scheduled_email",
        lambda to, deletion_scheduled_at_iso: captured.append((to, deletion_scheduled_at_iso)),
    )
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]

    await client.delete("/account/me", headers={"Authorization": f"Bearer {access_token}"})

    assert len(captured) == 1
    assert captured[0][0] == register_payload["email"]
    assert captured[0][1]  # a real ISO timestamp string was passed, not empty


async def test_account_restore_undoes_a_pending_deletion(client, register_payload, monkeypatch, db_session):
    captured = {}
    monkeypatch.setattr("api.services.account_restore.send_account_restore_email", lambda to, link: captured.update(link=link))

    await client.post("/auth/register", json=register_payload)
    access_token = (await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})).json()["access_token"]
    await client.delete("/account/me", headers={"Authorization": f"Bearer {access_token}"})

    # Simulate the pre-purge reminder (4.6) having already fired for this
    # deletion cycle, the way api/tasks/account_deletion_reminder.py
    # would set it.
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.deletion_reminder_sent_at = dt.datetime.now(dt.timezone.utc)
    await db_session.commit()

    # Still inside the grace period -- login is blocked...
    still_blocked = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert still_blocked.status_code == 401

    request = await client.post("/account/restore/request", json={"email": register_payload["email"]})
    assert request.status_code == 200
    restore_token = captured["link"].split("token=")[1]

    confirm = await client.post("/account/restore/confirm", json={"token": restore_token})
    assert confirm.status_code == 200

    # ...and now works again, with the original password (confirm never
    # issued its own tokens -- the user goes through the real login flow).
    restored_login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert restored_login.status_code == 200

    # 4.6: restoring cancels this deletion cycle entirely -- a LATER
    # deletion must be eligible for its own fresh reminder, not silently
    # skipped because this now-cancelled cycle already used one up.
    await db_session.refresh(user)
    assert user.deletion_reminder_sent_at is None


async def test_a_second_deletion_cycle_after_restore_resets_the_reminder_flag(client, register_payload, db_session):
    """4.6, the other half of the previous test's guarantee: restoring
    clears deletion_reminder_sent_at (proven above), but that alone
    isn't enough -- delete_account() itself must ALSO reset it on a
    fresh delete, for the case where a user deletes, restores, then
    deletes again WITHOUT the reminder ever having fired in between (so
    restore's own clearing never even ran on a non-None value). Without
    this, a stale non-None value from some other path could silently
    suppress the reminder for a deletion cycle that never got one."""
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    await client.delete("/account/me", headers=auth_header)

    # Simulate the reminder having already fired for THIS cycle.
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.deletion_reminder_sent_at = dt.datetime.now(dt.timezone.utc)
    await db_session.commit()

    await client.post("/account/restore/request", json={"email": register_payload["email"]})
    # (restore/confirm isn't needed here -- delete_account() itself is
    # what's under test; simulate the restored, active state directly.)
    user.is_active = True
    user.deleted_at = None
    user.deletion_scheduled_at = None
    await db_session.commit()

    access_token2 = (await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})).json()["access_token"]
    await client.delete("/account/me", headers={"Authorization": f"Bearer {access_token2}"})

    await db_session.refresh(user)
    assert user.deletion_reminder_sent_at is None


async def test_account_restore_request_is_silent_for_an_account_that_was_never_deleted(client, register_payload, monkeypatch):
    captured = {}
    monkeypatch.setattr("api.services.account_restore.send_account_restore_email", lambda to, link: captured.update(link=link))

    await client.post("/auth/register", json=register_payload)
    response = await client.post("/account/restore/request", json={"email": register_payload["email"]})
    assert response.status_code == 200  # same generic message either way
    assert "link" not in captured  # ...but no email was actually sent -- nothing to restore


async def test_account_restore_request_is_silent_for_unknown_email(client):
    response = await client.post("/account/restore/request", json={"email": "nobody@example.com"})
    assert response.status_code == 200


async def test_account_restore_token_cannot_be_reused(client, register_payload, monkeypatch):
    captured = {}
    monkeypatch.setattr("api.services.account_restore.send_account_restore_email", lambda to, link: captured.update(link=link))

    await client.post("/auth/register", json=register_payload)
    access_token = (await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})).json()["access_token"]
    await client.delete("/account/me", headers={"Authorization": f"Bearer {access_token}"})
    await client.post("/account/restore/request", json={"email": register_payload["email"]})
    restore_token = captured["link"].split("token=")[1]

    first = await client.post("/account/restore/confirm", json={"token": restore_token})
    assert first.status_code == 200

    # Deleting again and replaying the OLD token must not resurrect the
    # account a second time -- used_at was set on the first confirm.
    access_token2 = (await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})).json()["access_token"]
    await client.delete("/account/me", headers={"Authorization": f"Bearer {access_token2}"})

    replay = await client.post("/account/restore/confirm", json={"token": restore_token})
    assert replay.status_code == 400


async def test_account_restore_garbage_token_is_rejected(client):
    response = await client.post("/account/restore/confirm", json={"token": "this-was-never-issued"})
    assert response.status_code == 400


async def test_account_restore_expired_token_is_rejected(client, register_payload, monkeypatch, db_session):
    import datetime as dt

    from api.models.restore_token import AccountRestoreToken

    captured = {}
    monkeypatch.setattr("api.services.account_restore.send_account_restore_email", lambda to, link: captured.update(link=link))

    await client.post("/auth/register", json=register_payload)
    access_token = (await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})).json()["access_token"]
    await client.delete("/account/me", headers={"Authorization": f"Bearer {access_token}"})
    await client.post("/account/restore/request", json={"email": register_payload["email"]})
    restore_token = captured["link"].split("token=")[1]

    row = await db_session.scalar(select(AccountRestoreToken))
    row.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    await db_session.commit()

    response = await client.post("/account/restore/confirm", json={"token": restore_token})
    assert response.status_code == 400


async def test_account_restore_request_is_silent_once_the_grace_period_has_passed(client, register_payload, monkeypatch, db_session):
    """5.6 boundary: request_account_restore's guard is
    `deletion_scheduled_at > now`, not just `is_deleted` -- a row whose
    grace period has already elapsed but hasn't been hard-purged yet
    (api/tasks/account_purge.py runs on its own schedule, not
    instantly) must not get a working restore link either. Distinct
    from test_account_restore_request_is_silent_for_an_account_that_was_never_deleted
    above, which never sets deletion_scheduled_at at all -- this
    exercises the actual `> now` comparison."""
    from api.models.user import User

    captured = {}
    monkeypatch.setattr("api.services.account_restore.send_account_restore_email", lambda to, link: captured.update(link=link))

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    await client.delete("/account/me", headers={"Authorization": f"Bearer {access_token}"})

    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.deletion_scheduled_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    await db_session.commit()

    response = await client.post("/account/restore/request", json={"email": register_payload["email"]})
    assert response.status_code == 200  # same generic message either way
    assert "link" not in captured  # ...but no email was actually sent -- past its grace period


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


async def test_withdraw_consent_deactivates_account_without_scheduling_a_purge(client, register_payload, db_session):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    withdraw = await client.post("/account/consent/withdraw", headers=auth_header)
    assert withdraw.status_code == 200

    # Immediately locked out, same as a full delete would do...
    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert login.status_code == 401

    # ...but NOT scheduled for purge -- that's the whole distinction from
    # DELETE /account/me (1.1.10), checked directly against the DB since
    # nothing authenticated can read it back once the account is deactivated.
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    assert user.consent_withdrawn_at is not None
    assert user.is_active is False
    assert user.deleted_at is None
    assert user.deletion_scheduled_at is None


async def test_withdraw_consent_revokes_existing_sessions(client, register_payload, db_session):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    await client.post("/account/consent/withdraw", headers=auth_header)

    # 1.1.15: the blacklist row itself, checked directly -- same
    # reasoning as test_delete_account_soft_deletes_and_revokes_sessions.
    blacklisted = await db_session.scalar(select(RevokedAccessToken).where(RevokedAccessToken.jti == _jti_of(access_token)))
    assert blacklisted is not None

    refresh = await client.post("/auth/refresh", headers=_csrf(client))
    assert refresh.status_code == 401


async def test_withdraw_consent_twice_is_rejected(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    first = await client.post("/account/consent/withdraw", headers=auth_header)
    assert first.status_code == 200

    # The same access token is still cryptographically valid (JWTs aren't
    # revoked before their natural expiry) but is_active is now False, so
    # get_current_user itself rejects it before the handler ever runs.
    second = await client.post("/account/consent/withdraw", headers=auth_header)
    assert second.status_code == 401


async def test_consent_withdrawal_and_full_deletion_are_mutually_exclusive(client, register_payload):
    """api/models/user.py's comment on consent_withdrawn_at claims the
    field can never end up set at the same time as deleted_at, because
    both withdraw_consent() and delete_account() require is_active=True
    to be reached at all and each flips it False as their first effect.
    Proven directly, in both orders: whichever one fires first locks the
    other one out (401) for that account, using the SAME still-valid
    access token both times (is_active, not token validity, is what's
    blocking it)."""
    token_a = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    withdrew = await client.post("/account/consent/withdraw", headers={"Authorization": f"Bearer {token_a}"})
    assert withdrew.status_code == 200
    blocked_delete = await client.delete("/account/me", headers={"Authorization": f"Bearer {token_a}"})
    assert blocked_delete.status_code == 401

    other_payload = {**register_payload, "email": f"other-{register_payload['email']}"}
    token_b = (await client.post("/auth/register", json=other_payload)).json()["access_token"]
    deleted = await client.delete("/account/me", headers={"Authorization": f"Bearer {token_b}"})
    assert deleted.status_code == 200
    blocked_withdraw = await client.post("/account/consent/withdraw", headers={"Authorization": f"Bearer {token_b}"})
    assert blocked_withdraw.status_code == 401


async def test_consent_reactivation_undoes_a_withdrawal(client, register_payload, monkeypatch, db_session):
    captured = {}
    monkeypatch.setattr(
        "api.services.consent_reactivation.send_consent_reactivation_email",
        lambda to, link: captured.update(link=link),
    )

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    await client.post("/account/consent/withdraw", headers={"Authorization": f"Bearer {access_token}"})

    # Still deactivated -- consent withdrawal is not undone by itself.
    still_blocked = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert still_blocked.status_code == 401

    request = await client.post("/account/consent/reactivate/request", json={"email": register_payload["email"]})
    assert request.status_code == 200
    token = captured["link"].split("token=")[1]

    # accept_terms is required -- withdrawn consent can't come back silently.
    missing_consent = await client.post("/account/consent/reactivate/confirm", json={"token": token, "accept_terms": False})
    assert missing_consent.status_code == 422

    confirm = await client.post("/account/consent/reactivate/confirm", json={"token": token, "accept_terms": True})
    assert confirm.status_code == 200

    restored_login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert restored_login.status_code == 200

    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    assert user.consent_withdrawn_at is None
    assert user.is_active is True
    assert user.consent_given_at is not None


async def test_consent_reactivation_request_is_silent_for_an_account_that_never_withdrew(client, register_payload, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "api.services.consent_reactivation.send_consent_reactivation_email",
        lambda to, link: captured.update(link=link),
    )
    await client.post("/auth/register", json=register_payload)

    response = await client.post("/account/consent/reactivate/request", json={"email": register_payload["email"]})
    assert response.status_code == 200
    assert "link" not in captured


async def test_consent_reactivation_request_is_silent_for_unknown_email(client):
    response = await client.post("/account/consent/reactivate/request", json={"email": "nobody@example.com"})
    assert response.status_code == 200


async def test_consent_reactivation_does_not_apply_to_a_fully_deleted_account(client, register_payload, monkeypatch, db_session):
    """A row could in principle have both consent_withdrawn_at and
    deleted_at set (e.g. seeded directly, or a future code path) --
    reactivating consent must never be the thing that undoes a full
    account deletion. That's /account/restore/*'s job, not this one's."""
    captured = {}
    monkeypatch.setattr(
        "api.services.consent_reactivation.send_consent_reactivation_email",
        lambda to, link: captured.update(link=link),
    )
    import datetime as dt

    await client.post("/auth/register", json=register_payload)
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.consent_withdrawn_at = dt.datetime.now(dt.timezone.utc)
    user.is_active = False
    user.deleted_at = dt.datetime.now(dt.timezone.utc)
    user.deletion_scheduled_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30)
    await db_session.commit()

    response = await client.post("/account/consent/reactivate/request", json={"email": register_payload["email"]})
    assert response.status_code == 200
    assert "link" not in captured


async def test_consent_reactivation_token_cannot_be_reused(client, register_payload, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "api.services.consent_reactivation.send_consent_reactivation_email",
        lambda to, link: captured.update(link=link),
    )
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    await client.post("/account/consent/withdraw", headers={"Authorization": f"Bearer {access_token}"})
    await client.post("/account/consent/reactivate/request", json={"email": register_payload["email"]})
    token = captured["link"].split("token=")[1]

    first = await client.post("/account/consent/reactivate/confirm", json={"token": token, "accept_terms": True})
    assert first.status_code == 200

    # Withdraw again, then try to replay the OLD token.
    access_token2 = (await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})).json()["access_token"]
    await client.post("/account/consent/withdraw", headers={"Authorization": f"Bearer {access_token2}"})

    replay = await client.post("/account/consent/reactivate/confirm", json={"token": token, "accept_terms": True})
    assert replay.status_code == 400


async def test_consent_reactivation_garbage_token_is_rejected(client):
    response = await client.post("/account/consent/reactivate/confirm", json={"token": "this-was-never-issued", "accept_terms": True})
    assert response.status_code == 400


# ------------------------------------------------------------------ 4.3 --
async def test_stale_terms_version_blocks_a_substantive_endpoint(client, register_payload, monkeypatch):
    """4.3: once TERMS_VERSION changes, an account that consented under
    the OLD version must be blocked from ordinary service usage until it
    re-consents -- proven against a real substantive endpoint
    (PATCH /account/profile), not just asserted."""
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    still_current = await client.patch("/account/profile", json={"full_name": "Still Fine"}, headers=auth_header)
    assert still_current.status_code == 200

    monkeypatch.setattr(settings, "TERMS_VERSION", "2027-06-01-a-brand-new-version")

    blocked = await client.patch("/account/profile", json={"full_name": "Should Not Work"}, headers=auth_header)
    assert blocked.status_code == 403
    assert "accept-updated-terms" in blocked.json()["detail"]


async def test_accepting_updated_terms_unblocks_access_and_updates_the_record(client, register_payload, db_session, monkeypatch):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    monkeypatch.setattr(settings, "TERMS_VERSION", "2027-06-01-a-brand-new-version")
    assert (await client.patch("/account/profile", json={"full_name": "x"}, headers=auth_header)).status_code == 403

    accept = await client.post("/account/consent/accept-updated-terms", json={"accept_terms": True}, headers=auth_header)
    assert accept.status_code == 200

    now_works = await client.patch("/account/profile", json={"full_name": "Works Again"}, headers=auth_header)
    assert now_works.status_code == 200

    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    assert user.terms_version == "2027-06-01-a-brand-new-version"
    assert user.consent_given_at is not None


async def test_accepting_updated_terms_requires_explicit_true(client, register_payload, monkeypatch):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    monkeypatch.setattr(settings, "TERMS_VERSION", "2027-06-01-a-brand-new-version")

    response = await client.post("/account/consent/accept-updated-terms", json={"accept_terms": False}, headers=auth_header)
    assert response.status_code == 422


async def test_rgpd_rights_and_session_security_stay_reachable_despite_stale_terms(client, register_payload, monkeypatch):
    """4.3's exemptions, proven directly: an account stuck behind the
    stale-terms gate must still be able to exercise its actual RGPD
    rights and manage its own session security -- those can't be held
    hostage to accepting new terms first."""
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    monkeypatch.setattr(settings, "TERMS_VERSION", "2027-06-01-a-brand-new-version")

    assert (await client.get("/account/me", headers=auth_header)).status_code == 200
    assert (await client.get("/account/export", headers=auth_header)).status_code == 200
    assert (await client.get("/sessions", headers=auth_header)).status_code == 200

    session_id = (await client.get("/sessions", headers=auth_header)).json()[0]["id"]
    assert (await client.delete(f"/sessions/{session_id}", headers=auth_header)).status_code == 200


async def test_2fa_management_endpoints_stay_reachable_despite_stale_terms(client, register_payload, monkeypatch):
    """4.3's exemption extended to 2FA account security: each of these
    already requires either no prior 2FA state or a valid current TOTP
    code, so turning 2FA on/off or rotating recovery codes can't be held
    hostage to accepting new terms first, same reasoning as sessions
    above. Proven against all five endpoints -- /setup, /enable,
    /recovery-codes/status, /recovery-codes/regenerate, /disable, in the
    order a real client would actually call them -- while TERMS_VERSION
    is stale for the whole sequence."""
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    monkeypatch.setattr(settings, "TERMS_VERSION", "2027-06-01-a-brand-new-version")

    setup = await client.post("/auth/2fa/setup", headers=auth_header)
    assert setup.status_code == 200
    secret = setup.json()["secret"]

    enable = await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    assert enable.status_code == 200

    status_check = await client.get("/auth/2fa/recovery-codes/status", headers=auth_header)
    assert status_check.status_code == 200
    assert status_check.json() == {"total": 10, "remaining": 10}

    regenerate = await client.post("/auth/2fa/recovery-codes/regenerate", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    assert regenerate.status_code == 200

    disable = await client.post("/auth/2fa/disable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    assert disable.status_code == 200


async def test_delete_account_stays_reachable_despite_stale_terms(client, register_payload, monkeypatch):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    monkeypatch.setattr(settings, "TERMS_VERSION", "2027-06-01-a-brand-new-version")

    response = await client.delete("/account/me", headers=auth_header)
    assert response.status_code == 200


async def test_withdraw_consent_stays_reachable_despite_stale_terms(client, register_payload, monkeypatch):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    monkeypatch.setattr(settings, "TERMS_VERSION", "2027-06-01-a-brand-new-version")

    response = await client.post("/account/consent/withdraw", headers=auth_header)
    assert response.status_code == 200


# --------------------------------------------------------------- 1.1.13 --
async def test_update_profile_fields(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.patch(
        "/account/profile", json={"full_name": "Ada K. Lovelace", "company": "Analytical Engines Ltd"}, headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Ada K. Lovelace"
    assert response.json()["company"] == "Analytical Engines Ltd"


async def test_set_password_lets_an_oauth_only_account_add_a_fallback_login(client, db_session, monkeypatch):
    """An OAuth-only account (hashed_password is None, see api/models/user.py)
    has no fallback if it loses access to its linked provider -- this is
    the fix for that. There's no real browser OAuth flow to drive here
    (see test_oauth_logic_integration.py's docstring), so the account and
    its "already logged in" access token are constructed directly, the
    same way that file tests _find_or_create_user() without a browser."""
    from api.security.jwt import create_access_token

    captured = []
    monkeypatch.setattr("api.routers.account.send_password_set_email", lambda to: captured.append(to))

    # terms_version/consent_given_at set explicitly -- a REAL OAuth
    # sign-up backfills these (api/routers/oauth.py's _find_or_create_user,
    # 4.2), and get_current_user (4.3) now requires a current
    # terms_version to let a request through at all.
    oauth_user = User(
        email="oauth-only@example.com", hashed_password=None, is_email_verified=True,
        terms_version=settings.TERMS_VERSION, consent_given_at=dt.datetime.now(dt.timezone.utc),
    )
    db_session.add(oauth_user)
    await db_session.commit()
    access_token, _jti = create_access_token(oauth_user.id)
    auth_header = {"Authorization": f"Bearer {access_token}"}

    set_password = await client.post("/account/set-password", json={"new_password": "a-brand-new-password"}, headers=auth_header)
    assert set_password.status_code == 200
    assert captured == ["oauth-only@example.com"]

    # Now works as a genuine fallback: a normal password login succeeds.
    login = await client.post("/auth/login", json={"email": "oauth-only@example.com", "password": "a-brand-new-password"})
    assert login.status_code == 200


async def test_set_password_is_rejected_for_an_account_that_already_has_one(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.post(
        "/account/set-password", json={"new_password": "another-password"}, headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 400


# ----------------------------------------------------------- monitoring --
async def test_health_ready_reports_database_and_redis_status(client):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"database", "rate_limit_redis"}
    # Both real services are reachable in this dev/test environment --
    # a genuinely down dependency is exercised at the unit level in
    # tests/test_rate_limiting_integration.py's fail-open test instead of
    # here, since actually taking Postgres or Redis offline mid-suite
    # isn't something this test file can safely simulate.
    assert body["database"] == "ok"
    assert body["rate_limit_redis"] == "ok"
