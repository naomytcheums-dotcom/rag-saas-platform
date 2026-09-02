"""
Audit finding 27, tested end to end against a REAL local OIDC identity
provider (tests/oidc_test_idp.py) -- a genuine RSA keypair, a real
/.well-known/openid-configuration + JWKS endpoint served over an actual
HTTP socket, and RS256-signed id_tokens. Unlike
tests/test_oauth_logic_integration.py's Google/GitHub tests (which only
exercise _find_or_create_user directly, because nothing can automate a
real Google/GitHub consent screen -- see that file's own docstring), the
generic-OIDC choice for enterprise SSO (api/models/enterprise_sso.py's
module docstring) makes the FULL authorize -> callback -> token-exchange
-> JWKS-verified id_token flow genuinely testable without a human, which
is exactly what happens here: every HTTP call api/routers/enterprise_sso.py
and api/security/enterprise_oidc.py make is real, nothing is mocked at
the network or crypto layer.

Account data via the fast SQLite `client`/`db_session` fixtures
(conftest.py) -- same split as every other integration file in this
suite (real infra for the thing under test, SQLite for the rest).
"""

import asyncio
import sys
import uuid
from pathlib import Path

import pyotp
import pytest
import uvicorn
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oidc_test_idp import create_app, register_authorization_code  # noqa: E402

from api.config import settings  # noqa: E402
from api.models.user import User, UserRole  # noqa: E402

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture(autouse=True)
def _ensure_secret_encryption_key(monkeypatch):
    """SECRET_ENCRYPTION_KEY is optional until a feature that needs it is
    actually used (see api/config.py's comment) -- unset in this dev
    .env, since nothing else in the suite needs it. A fixed, valid Fernet
    key for this whole test module only."""
    if not settings.SECRET_ENCRYPTION_KEY:
        from cryptography.fernet import Fernet
        monkeypatch.setattr(settings, "SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())


@pytest.fixture(scope="module")
def oidc_idp():
    """
    One real local OIDC server for the whole module, run in its own
    background thread with its OWN event loop -- deliberately NOT an
    asyncio.create_task() on the same loop the `client` fixture's
    ASGITransport (httpx's anyio backend) and this test module share.
    That combination was tried first and produced consistent
    httpx.ReadTimeout failures: the in-process ASGI client's own nested
    real-socket calls into this server (api/security/enterprise_oidc.py's
    httpx/Authlib calls, made FROM INSIDE a route handler the `client`
    fixture is already awaiting) starved the same-loop uvicorn task of
    turns badly enough that it never got to accept/respond in time. A
    genuinely separate thread + event loop sidesteps that class of
    scheduling interaction entirely, and is the standard way to stand up
    a real server for a test that also drives an in-process ASGI client
    of its own.
    """
    import threading

    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=lambda: asyncio.run(server.serve()), daemon=True)
    thread.start()
    while not server.started:
        import time
        time.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    app.state.idp["issuer"] = f"http://127.0.0.1:{port}"

    yield app

    server.should_exit = True
    thread.join(timeout=5)


async def _promote_to_admin(db_session, email: str) -> None:
    user = await db_session.scalar(select(User).where(User.email == email))
    user.role = UserRole.admin
    await db_session.commit()


async def _make_admin(client, db_session, register_payload) -> str:
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    await _promote_to_admin(db_session, register_payload["email"])
    return access_token


async def _create_connection(client, admin_token, oidc_idp, *, email_domain="acme.com", client_id="test-client-id"):
    response = await client.post(
        "/admin/sso/connections",
        json={
            "email_domain": email_domain, "display_name": "Acme Corp SSO",
            "issuer": oidc_idp.state.idp["issuer"], "client_id": client_id, "client_secret": "test-client-secret",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _extract_state(authorize_response) -> str:
    location = authorize_response.headers["location"]
    return location.split("state=")[1].split("&")[0]


async def test_non_admin_cannot_create_sso_connections(client, register_payload, oidc_idp):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.post(
        "/admin/sso/connections",
        json={"email_domain": "acme.com", "display_name": "Acme", "issuer": oidc_idp.state.idp["issuer"],
              "client_id": "x", "client_secret": "y"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 404


async def test_admin_can_create_and_list_connections(monkeypatch, client, db_session, register_payload, oidc_idp):
    captured = []
    monkeypatch.setattr("api.routers.enterprise_sso.send_enterprise_sso_connection_created_email", lambda *a: captured.append(a))

    admin_token = await _make_admin(client, db_session, register_payload)
    created = await _create_connection(client, admin_token, oidc_idp)
    assert created["email_domain"] == "acme.com"
    assert "client_secret" not in created

    listed = await client.get("/admin/sso/connections", headers={"Authorization": f"Bearer {admin_token}"})
    assert listed.status_code == 200
    assert any(item["id"] == created["id"] for item in listed.json()["items"])
    assert len(captured) == 1


async def test_creating_a_second_connection_for_the_same_domain_is_rejected(client, db_session, register_payload, oidc_idp):
    admin_token = await _make_admin(client, db_session, register_payload)
    await _create_connection(client, admin_token, oidc_idp, email_domain="dupe.com")

    response = await client.post(
        "/admin/sso/connections",
        json={"email_domain": "dupe.com", "display_name": "Dupe Inc", "issuer": oidc_idp.state.idp["issuer"],
              "client_id": "another-client", "client_secret": "another-secret"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409


async def test_admin_can_delete_a_connection(client, db_session, register_payload, oidc_idp):
    admin_token = await _make_admin(client, db_session, register_payload)
    connection = await _create_connection(client, admin_token, oidc_idp, email_domain="deleteme.com")

    deleted = await client.delete(f"/admin/sso/connections/{connection['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert deleted.status_code == 200

    authorize = await client.get(f"/auth/sso/{connection['id']}/authorize")
    assert authorize.status_code == 404


async def test_discover_reports_availability_correctly(client, db_session, register_payload, oidc_idp):
    admin_token = await _make_admin(client, db_session, register_payload)
    await _create_connection(client, admin_token, oidc_idp, email_domain="discoverable.com")

    available = await client.post("/auth/sso/discover", json={"email": "someone@discoverable.com"})
    assert available.status_code == 200
    assert available.json()["sso_available"] is True
    assert available.json()["display_name"] == "Acme Corp SSO"

    unavailable = await client.post("/auth/sso/discover", json={"email": "someone@not-configured.com"})
    assert unavailable.json()["sso_available"] is False


async def test_full_sso_login_creates_a_new_user_and_issues_a_real_session(client, db_session, register_payload, oidc_idp):
    admin_token = await _make_admin(client, db_session, register_payload)
    connection = await _create_connection(client, admin_token, oidc_idp, email_domain="newco.com", client_id="newco-client")

    user_email = f"sso-newuser-{uuid.uuid4().hex[:8]}@newco.com"
    code = f"code-{uuid.uuid4().hex}"
    register_authorization_code(oidc_idp, code, sub=f"sub-{uuid.uuid4().hex}", email=user_email, audience="newco-client")

    authorize = await client.get(f"/auth/sso/{connection['id']}/authorize")
    assert authorize.status_code == 302
    state = _extract_state(authorize)

    callback = await client.get(f"/auth/sso/{connection['id']}/callback", params={"code": code, "state": state})
    assert callback.status_code == 302, callback.text
    location = callback.headers["location"]
    assert "mfa_required" not in location
    assert "access_token=" in location
    access_token = location.split("access_token=")[1].split("&")[0]

    me = await client.get("/account/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.status_code == 200
    assert me.json()["email"] == user_email

    created_user = await db_session.scalar(select(User).where(User.email == user_email))
    assert created_user is not None
    assert created_user.hashed_password is None  # SSO-only account
    assert created_user.is_email_verified is True


async def test_sso_login_links_to_an_existing_verified_password_account(client, db_session, oidc_idp):
    admin_payload = {"email": f"sso-admin-{uuid.uuid4().hex[:8]}@example.com", "password": "correct-horse-battery-staple", "accept_terms": True}
    admin_token = await _make_admin(client, db_session, admin_payload)
    connection = await _create_connection(client, admin_token, oidc_idp, email_domain="linkco.com", client_id="linkco-client")

    existing_email = f"sso-link-{uuid.uuid4().hex[:8]}@linkco.com"
    await client.post("/auth/register", json={"email": existing_email, "password": "correct-horse-battery-staple", "accept_terms": True})

    code = f"code-{uuid.uuid4().hex}"
    register_authorization_code(oidc_idp, code, sub=f"sub-{uuid.uuid4().hex}", email=existing_email, audience="linkco-client")

    authorize = await client.get(f"/auth/sso/{connection['id']}/authorize")
    state = _extract_state(authorize)
    callback = await client.get(f"/auth/sso/{connection['id']}/callback", params={"code": code, "state": state})
    assert callback.status_code == 302
    assert "access_token=" in callback.headers["location"]

    matching_users = (await db_session.scalars(select(User).where(User.email == existing_email))).all()
    assert len(matching_users) == 1  # linked, not duplicated
    assert matching_users[0].is_email_verified is True


async def test_sso_login_is_rejected_when_the_email_domain_does_not_match_the_connection(client, db_session, register_payload, oidc_idp):
    """The security check unique to enterprise SSO (vs. Google/GitHub's
    fixed-provider OAuth): an IdP asserting an email OUTSIDE the domain
    an admin scoped this connection to must not be trusted, even though
    the token itself is genuinely, correctly signed by that same IdP."""
    admin_token = await _make_admin(client, db_session, register_payload)
    connection = await _create_connection(client, admin_token, oidc_idp, email_domain="scoped.com", client_id="scoped-client")

    code = f"code-{uuid.uuid4().hex}"
    register_authorization_code(oidc_idp, code, sub="sub-mismatch", email="someone@totally-different-domain.com", audience="scoped-client")

    authorize = await client.get(f"/auth/sso/{connection['id']}/authorize")
    state = _extract_state(authorize)
    callback = await client.get(f"/auth/sso/{connection['id']}/callback", params={"code": code, "state": state})
    assert callback.status_code == 400

    orphan = await db_session.scalar(select(User).where(User.email == "someone@totally-different-domain.com"))
    assert orphan is None  # no account was created for the unauthorized domain


async def test_sso_login_rejects_a_token_with_the_wrong_audience(client, db_session, register_payload, oidc_idp):
    """A real IdP could conceivably issue tokens for MULTIPLE client_ids
    (multiple apps registered against the same tenant) -- a token meant
    for a different client_id must not be accepted for this connection,
    same "aud claim actually checked" property RS256/OIDC validation
    exists to provide."""
    admin_token = await _make_admin(client, db_session, register_payload)
    connection = await _create_connection(client, admin_token, oidc_idp, email_domain="audience.com", client_id="expected-client-id")

    code = f"code-{uuid.uuid4().hex}"
    # Token is signed for a DIFFERENT audience than the connection's client_id.
    register_authorization_code(oidc_idp, code, sub="sub-aud", email="user@audience.com", audience="some-other-client-id")

    authorize = await client.get(f"/auth/sso/{connection['id']}/authorize")
    state = _extract_state(authorize)
    callback = await client.get(f"/auth/sso/{connection['id']}/callback", params={"code": code, "state": state})
    assert callback.status_code == 400


async def test_sso_login_state_mismatch_is_rejected(client, db_session, register_payload, oidc_idp):
    admin_token = await _make_admin(client, db_session, register_payload)
    connection = await _create_connection(client, admin_token, oidc_idp, email_domain="csrf.com", client_id="csrf-client")

    code = f"code-{uuid.uuid4().hex}"
    register_authorization_code(oidc_idp, code, sub="sub-csrf", email="user@csrf.com", audience="csrf-client")

    await client.get(f"/auth/sso/{connection['id']}/authorize")  # establishes the session's real expected state
    callback = await client.get(f"/auth/sso/{connection['id']}/callback", params={"code": code, "state": "forged-state-value"})
    assert callback.status_code == 400


async def test_sso_login_with_an_invalid_code_fails_cleanly(client, db_session, register_payload, oidc_idp):
    admin_token = await _make_admin(client, db_session, register_payload)
    connection = await _create_connection(client, admin_token, oidc_idp, email_domain="badcode.com", client_id="badcode-client")

    authorize = await client.get(f"/auth/sso/{connection['id']}/authorize")
    state = _extract_state(authorize)
    callback = await client.get(f"/auth/sso/{connection['id']}/callback", params={"code": "never-registered", "state": state})
    assert callback.status_code == 400


async def test_sso_login_reports_mfa_required_for_an_account_with_totp_enabled(client, db_session, oidc_idp):
    admin_payload = {"email": f"sso-admin2-{uuid.uuid4().hex[:8]}@example.com", "password": "correct-horse-battery-staple", "accept_terms": True}
    admin_token = await _make_admin(client, db_session, admin_payload)
    connection = await _create_connection(client, admin_token, oidc_idp, email_domain="mfaco.com", client_id="mfaco-client")

    mfa_email = f"sso-mfa-{uuid.uuid4().hex[:8]}@mfaco.com"
    register = await client.post("/auth/register", json={"email": mfa_email, "password": "correct-horse-battery-staple", "accept_terms": True})
    user_access_token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {user_access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=headers)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=headers)

    code = f"code-{uuid.uuid4().hex}"
    register_authorization_code(oidc_idp, code, sub=f"sub-{uuid.uuid4().hex}", email=mfa_email, audience="mfaco-client")

    authorize = await client.get(f"/auth/sso/{connection['id']}/authorize")
    state = _extract_state(authorize)
    callback = await client.get(f"/auth/sso/{connection['id']}/callback", params={"code": code, "state": state})
    assert callback.status_code == 302
    location = callback.headers["location"]
    assert "mfa_required=true" in location
    assert "access_token=" not in location
    assert "methods=totp" in location
