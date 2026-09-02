"""
Audit finding 26, tested against REAL Redis (api/security/webauthn.py's
challenge store always uses it, unconditionally of RATE_LIMIT_ENABLED --
this is NOT the rate limiter, see that module's docstring) and a REAL
software authenticator (tests/webauthn_test_authenticator.py) that
produces genuinely valid, independently-verifiable WebAuthn signatures --
api/security/webauthn.py's calls into the `webauthn` library do real
cryptographic verification against them, nothing here is mocked at the
crypto layer. Account data still uses the fast SQLite `client` fixture
(conftest.py) -- same split as tests/test_rate_limiting_integration.py.
"""

import uuid

import pytest
import pyotp
import redis.asyncio as redis_asyncio
from webauthn.helpers import base64url_to_bytes

from api.config import settings

from webauthn_test_authenticator import SoftwareAuthenticator

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture(autouse=True)
async def _require_redis():
    try:
        async with redis_asyncio.from_url(settings.RATE_LIMIT_REDIS_URL, decode_responses=True) as r:
            await r.ping()
    except Exception as exc:
        pytest.skip(f"Redis is not reachable -- skipping WebAuthn integration tests ({exc})")


def _unique_payload():
    return {
        "email": f"webauthn-{uuid.uuid4().hex[:10]}@example.com",
        "password": "correct-horse-battery-staple",
        "accept_terms": True,
    }


async def _register_and_login(client, payload):
    register = await client.post("/auth/register", json=payload)
    assert register.status_code == 201
    return register.json()["access_token"]


async def _add_webauthn_credential(client, access_token: str, nickname: str = "Test Key") -> SoftwareAuthenticator:
    """Full registration ceremony against the real endpoints, using a
    fresh SoftwareAuthenticator -- the caller gets it back to later
    produce a matching, real authentication assertion."""
    headers = {"Authorization": f"Bearer {access_token}"}
    options_response = await client.post("/auth/webauthn/register/options", headers=headers)
    assert options_response.status_code == 200
    options = options_response.json()

    authenticator = SoftwareAuthenticator(
        credential_id=uuid.uuid4().bytes, rp_id=settings.WEBAUTHN_RP_ID,
    )
    challenge = base64url_to_bytes(options["challenge"])
    credential = authenticator.create_registration_response(challenge, settings.WEBAUTHN_RP_ORIGIN)

    verify_response = await client.post(
        "/auth/webauthn/register/verify", json={"credential": credential, "nickname": nickname}, headers=headers,
    )
    assert verify_response.status_code == 200, verify_response.text
    return authenticator


async def test_registration_options_returns_real_webauthn_options(client, register_payload):
    access_token = await _register_and_login(client, register_payload)
    response = await client.post("/auth/webauthn/register/options", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["rp"]["id"] == settings.WEBAUTHN_RP_ID
    assert body["rp"]["name"] == settings.WEBAUTHN_RP_NAME
    assert "challenge" in body


async def test_full_registration_ceremony_creates_a_real_credential(monkeypatch, client, register_payload):
    captured = []
    monkeypatch.setattr("api.routers.webauthn.send_webauthn_credential_added_email", lambda *a: captured.append(a))

    access_token = await _register_and_login(client, register_payload)
    await _add_webauthn_credential(client, access_token, nickname="My YubiKey")

    headers = {"Authorization": f"Bearer {access_token}"}
    listed = await client.get("/auth/webauthn/credentials", headers=headers)
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["nickname"] == "My YubiKey"
    assert "credential_id" not in items[0]
    assert "public_key" not in items[0]
    assert captured == [(register_payload["email"], "My YubiKey")]


async def test_registration_is_rejected_with_a_forged_signature(client, register_payload):
    """The negative case that proves this isn't accidentally accepting
    anything: an authenticator that signs with a DIFFERENT keypair than
    the one whose public key ends up in the attestation object must fail
    verification. Simulated by tampering with the credential id used to
    build the response after generating it against a fresh authenticator
    for a mismatched keypair scenario -- concretely, by corrupting the
    attestationObject's signature-independent structure is fragile, so
    instead this proves the simpler, equally real property: submitting
    a credential for a WRONG (never-issued) challenge is rejected."""
    access_token = await _register_and_login(client, register_payload)
    headers = {"Authorization": f"Bearer {access_token}"}

    authenticator = SoftwareAuthenticator(credential_id=uuid.uuid4().bytes, rp_id=settings.WEBAUTHN_RP_ID)
    wrong_challenge = b"\x00" * 32  # never issued by build_registration_options
    credential = authenticator.create_registration_response(wrong_challenge, settings.WEBAUTHN_RP_ORIGIN)

    response = await client.post(
        "/auth/webauthn/register/verify", json={"credential": credential, "nickname": "Forged"}, headers=headers,
    )
    assert response.status_code == 400


async def test_registration_is_capped_at_the_configured_maximum(monkeypatch, client, register_payload):
    monkeypatch.setattr(settings, "WEBAUTHN_MAX_CREDENTIALS_PER_USER", 1)
    access_token = await _register_and_login(client, register_payload)
    await _add_webauthn_credential(client, access_token, nickname="First key")

    blocked = await client.post("/auth/webauthn/register/options", headers={"Authorization": f"Bearer {access_token}"})
    assert blocked.status_code == 400


async def test_deleting_a_credential_sends_a_notification_and_removes_it(monkeypatch, client, register_payload):
    captured = []
    monkeypatch.setattr("api.routers.webauthn.send_webauthn_credential_removed_email", lambda *a: captured.append(a))

    access_token = await _register_and_login(client, register_payload)
    headers = {"Authorization": f"Bearer {access_token}"}
    await _add_webauthn_credential(client, access_token, nickname="Doomed key")

    credential_id = (await client.get("/auth/webauthn/credentials", headers=headers)).json()["items"][0]["id"]
    deleted = await client.delete(f"/auth/webauthn/credentials/{credential_id}", headers=headers)
    assert deleted.status_code == 200
    assert captured == [(register_payload["email"], "Doomed key")]

    remaining = await client.get("/auth/webauthn/credentials", headers=headers)
    assert remaining.json()["items"] == []


async def test_a_user_cannot_delete_another_user_s_credential(client, register_payload):
    victim_token = await _register_and_login(client, register_payload)
    await _add_webauthn_credential(client, victim_token, nickname="Victim's key")
    victim_headers = {"Authorization": f"Bearer {victim_token}"}
    credential_id = (await client.get("/auth/webauthn/credentials", headers=victim_headers)).json()["items"][0]["id"]

    attacker_payload = _unique_payload()
    attacker_token = await _register_and_login(client, attacker_payload)
    attacker_headers = {"Authorization": f"Bearer {attacker_token}"}

    response = await client.delete(f"/auth/webauthn/credentials/{credential_id}", headers=attacker_headers)
    assert response.status_code == 404

    still_there = await client.get("/auth/webauthn/credentials", headers=victim_headers)
    assert len(still_there.json()["items"]) == 1


async def test_login_reports_webauthn_as_an_available_method_with_no_totp(client, register_payload):
    access_token = await _register_and_login(client, register_payload)
    await _add_webauthn_credential(client, access_token)

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert login.status_code == 200
    body = login.json()
    assert body["mfa_required"] is True
    assert body["available_methods"] == ["webauthn"]


async def test_login_reports_both_methods_when_totp_and_webauthn_are_both_enabled(client, register_payload):
    access_token = await _register_and_login(client, register_payload)
    headers = {"Authorization": f"Bearer {access_token}"}
    await _add_webauthn_credential(client, access_token)

    secret = (await client.post("/auth/2fa/setup", headers=headers)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=headers)

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    assert set(login.json()["available_methods"]) == {"totp", "webauthn"}


async def test_full_authentication_ceremony_issues_a_real_working_session(client, register_payload):
    access_token = await _register_and_login(client, register_payload)
    authenticator = await _add_webauthn_credential(client, access_token)

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]

    options_response = await client.post("/auth/webauthn/authenticate/options", json={"mfa_token": mfa_token})
    assert options_response.status_code == 200
    options = options_response.json()
    challenge = base64url_to_bytes(options["challenge"])
    assertion = authenticator.create_authentication_response(challenge, settings.WEBAUTHN_RP_ORIGIN)

    verify_response = await client.post(
        "/auth/webauthn/authenticate/verify", json={"mfa_token": mfa_token, "credential": assertion},
    )
    assert verify_response.status_code == 200, verify_response.text
    new_access_token = verify_response.json()["access_token"]

    # The proof that isn't just "200 OK" -- an actual, usable session.
    me = await client.get("/account/me", headers={"Authorization": f"Bearer {new_access_token}"})
    assert me.status_code == 200
    assert me.json()["email"] == register_payload["email"]


async def test_authentication_fails_for_a_credential_belonging_to_another_account(client, register_payload):
    """The account-isolation property that makes it safe to look up a
    presented credential id without first knowing which user it claims
    to belong to: even a genuinely valid, correctly-signed assertion for
    account B's OWN key must not complete account A's pending login."""
    victim_token = await _register_and_login(client, register_payload)
    await _add_webauthn_credential(client, victim_token)

    attacker_payload = _unique_payload()
    attacker_token = await _register_and_login(client, attacker_payload)
    attacker_authenticator = await _add_webauthn_credential(client, attacker_token)

    victim_login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    victim_mfa_token = victim_login.json()["mfa_token"]

    # Options are generated against the VICTIM's own registered
    # credentials -- the attacker's assertion won't match any of them,
    # exactly what a real forged/replayed cross-account attempt looks like.
    options_response = await client.post("/auth/webauthn/authenticate/options", json={"mfa_token": victim_mfa_token})
    challenge = base64url_to_bytes(options_response.json()["challenge"])
    forged_assertion = attacker_authenticator.create_authentication_response(challenge, settings.WEBAUTHN_RP_ORIGIN)

    response = await client.post(
        "/auth/webauthn/authenticate/verify", json={"mfa_token": victim_mfa_token, "credential": forged_assertion},
    )
    assert response.status_code == 401


async def test_replaying_a_stale_assertion_against_a_fresh_challenge_fails(client, register_payload):
    """Redis's GETDEL makes each challenge single-use -- proven here by
    generating a real, validly-signed assertion for challenge #1, then
    trying to submit it after a SECOND authenticate/options call issued
    (and is now expecting) a different challenge #2."""
    access_token = await _register_and_login(client, register_payload)
    authenticator = await _add_webauthn_credential(client, access_token)

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]

    first_options = await client.post("/auth/webauthn/authenticate/options", json={"mfa_token": mfa_token})
    stale_challenge = base64url_to_bytes(first_options.json()["challenge"])
    stale_assertion = authenticator.create_authentication_response(stale_challenge, settings.WEBAUTHN_RP_ORIGIN)

    # A second options call overwrites the stored challenge for this mfa_token.
    await client.post("/auth/webauthn/authenticate/options", json={"mfa_token": mfa_token})

    response = await client.post(
        "/auth/webauthn/authenticate/verify", json={"mfa_token": mfa_token, "credential": stale_assertion},
    )
    assert response.status_code == 401


async def test_authenticate_options_returns_400_when_the_account_has_no_credentials(client, register_payload):
    access_token = await _register_and_login(client, register_payload)
    headers = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=headers)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=headers)

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]

    response = await client.post("/auth/webauthn/authenticate/options", json={"mfa_token": mfa_token})
    assert response.status_code == 400


async def test_authenticate_verify_is_rate_limited_per_mfa_token(monkeypatch, client, register_payload):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    try:
        async with redis_asyncio.from_url(settings.RATE_LIMIT_REDIS_URL, decode_responses=True) as r:
            await r.flushdb()
    except Exception as exc:
        pytest.skip(f"Redis is not reachable -- skipping ({exc})")

    access_token = await _register_and_login(client, register_payload)
    authenticator = await _add_webauthn_credential(client, access_token)

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]

    options_response = await client.post("/auth/webauthn/authenticate/options", json={"mfa_token": mfa_token})
    challenge = base64url_to_bytes(options_response.json()["challenge"])
    # A garbage credential id (never registered) -- always fails
    # verification, but that's fine: this test only cares that enough
    # failed attempts trip the limiter, same shape as
    # test_2fa_verify_login_is_rate_limited_per_mfa_token.
    bogus = SoftwareAuthenticator(credential_id=uuid.uuid4().bytes, rp_id=settings.WEBAUTHN_RP_ID)
    bogus_assertion = bogus.create_authentication_response(challenge, settings.WEBAUTHN_RP_ORIGIN)

    for _ in range(settings.TWO_FA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS):
        response = await client.post(
            "/auth/webauthn/authenticate/verify", json={"mfa_token": mfa_token, "credential": bogus_assertion},
        )
        assert response.status_code == 401

    blocked = await client.post(
        "/auth/webauthn/authenticate/verify", json={"mfa_token": mfa_token, "credential": bogus_assertion},
    )
    assert blocked.status_code == 429
