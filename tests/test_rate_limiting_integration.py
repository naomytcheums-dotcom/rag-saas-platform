"""
Rate limiting (brute-force / spam protection on the 5 endpoints an
attacker would actually target), tested against a REAL Redis --
tests/conftest.py's autouse fixture disables RATE_LIMIT_ENABLED for
every other test file in the suite, so every test here explicitly
re-enables it for itself. Uses the SQLite-backed `client` fixture from
conftest.py for the account data (rate limiting doesn't care which
database backs the accounts), but real Redis for the counters.
"""

import uuid

import pytest
import redis.asyncio as redis_asyncio

from api.config import settings
from api.security import rate_limit as rate_limit_module

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture(autouse=True)
async def _enable_rate_limiting(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    try:
        async with redis_asyncio.from_url(settings.RATE_LIMIT_REDIS_URL, decode_responses=True) as r:
            await r.ping()
            # RATE_LIMIT_REDIS_URL points at its own dedicated Redis DB
            # number (see api/config.py's comment), so a full flush here
            # is safe -- nothing else uses this DB. Without this, tests
            # that don't set a unique X-Forwarded-For (most of them --
            # only the IP-limit tests need to) would all share counters
            # for the default test-client IP and the fixed register_payload
            # email, causing one test's calls to trip a LATER test's limit.
            await r.flushdb()
    except Exception as exc:
        pytest.skip(f"Redis is not reachable at RATE_LIMIT_REDIS_URL -- skipping rate limiting tests ({exc})")


async def test_login_is_rate_limited_by_ip(client, register_payload):
    # The Redis DB is flushed before every test (see _enable_rate_limiting
    # above), so a fixed IP/email pair is safe here -- no cross-test leakage.
    headers = {"X-Forwarded-For": "203.0.113.10"}
    await client.post("/auth/register", json=register_payload, headers=headers)

    for _ in range(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS):
        response = await client.post(
            "/auth/login", json={"email": register_payload["email"], "password": "wrong-password"}, headers=headers,
        )
        assert response.status_code == 401  # wrong password, but still under the limit

    blocked = await client.post(
        "/auth/login", json={"email": register_payload["email"], "password": "wrong-password"}, headers=headers,
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


async def test_login_is_rate_limited_by_email_across_different_ips(client, register_payload):
    """Same target email, a different fake IP on every request -- proves
    the email-based limit catches a distributed attack that IP-based
    limiting alone would miss."""
    await client.post("/auth/register", json=register_payload)

    for i in range(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS):
        response = await client.post(
            "/auth/login",
            json={"email": register_payload["email"], "password": "wrong-password"},
            headers={"X-Forwarded-For": f"198.51.100.{i + 1}"},
        )
        assert response.status_code == 401

    blocked = await client.post(
        "/auth/login",
        json={"email": register_payload["email"], "password": "wrong-password"},
        headers={"X-Forwarded-For": "198.51.100.250"},  # yet another new IP
    )
    assert blocked.status_code == 429


async def test_register_is_rate_limited_by_ip(client):
    headers = {"X-Forwarded-For": "203.0.113.20"}
    for i in range(settings.REGISTER_RATE_LIMIT_MAX_ATTEMPTS):
        response = await client.post("/auth/register", json={
            "email": f"ratelimit-register-{uuid.uuid4().hex[:8]}@example.com",
            "password": "correct-horse-battery-staple", "accept_terms": True,
        }, headers=headers)
        assert response.status_code == 201

    blocked = await client.post("/auth/register", json={
        "email": f"ratelimit-register-{uuid.uuid4().hex[:8]}@example.com",
        "password": "correct-horse-battery-staple", "accept_terms": True,
    }, headers=headers)
    assert blocked.status_code == 429


async def test_password_forgot_is_rate_limited_by_email(client, register_payload):
    await client.post("/auth/register", json=register_payload)

    for _ in range(settings.PASSWORD_FORGOT_RATE_LIMIT_MAX_ATTEMPTS):
        response = await client.post("/auth/password/forgot", json={"email": register_payload["email"]})
        assert response.status_code == 200

    blocked = await client.post("/auth/password/forgot", json={"email": register_payload["email"]})
    assert blocked.status_code == 429


async def test_verify_email_request_is_rate_limited_by_email(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    # register() already sent one verification email -- that counts too,
    # since it goes through the same create_and_send_email_otp() path...
    # but NOT through this rate-limited /request endpoint, so it doesn't
    # consume this endpoint's quota. Confirmed by the loop below using
    # exactly the configured max and still succeeding every time.
    for _ in range(settings.EMAIL_VERIFY_REQUEST_RATE_LIMIT_MAX_ATTEMPTS):
        response = await client.post("/auth/verify-email/request", headers=auth_header)
        assert response.status_code == 200

    blocked = await client.post("/auth/verify-email/request", headers=auth_header)
    assert blocked.status_code == 429


async def test_2fa_verify_login_is_rate_limited_per_mfa_token(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    import pyotp
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]

    for _ in range(settings.TWO_FA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS):
        response = await client.post("/auth/2fa/verify-login", json={"mfa_token": mfa_token, "code": "000000"})
        assert response.status_code == 401  # wrong code, but still under the limit

    blocked = await client.post("/auth/2fa/verify-login", json={"mfa_token": mfa_token, "code": "000000"})
    assert blocked.status_code == 429


async def test_rate_limiting_fails_open_when_redis_is_unreachable(monkeypatch):
    """The core design decision (see api/security/rate_limit.py's
    docstring): a Redis outage degrades brute-force protection, it must
    never take down login/register/etc. entirely."""
    broken_client = redis_asyncio.from_url("redis://127.0.0.1:1/0", decode_responses=True, socket_connect_timeout=1)
    monkeypatch.setattr(rate_limit_module, "_redis", broken_client)

    # Must NOT raise, despite Redis being unreachable.
    await rate_limit_module.enforce_rate_limit("ratelimit:test:unreachable", max_attempts=1, window_seconds=60)
