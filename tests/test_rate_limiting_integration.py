"""
Rate limiting (brute-force / spam protection on the 5 endpoints an
attacker would actually target), tested against a REAL Redis --
tests/conftest.py's autouse fixture disables RATE_LIMIT_ENABLED for
every other test file in the suite, so every test here explicitly
re-enables it for itself. Uses the SQLite-backed `client` fixture from
conftest.py for the account data (rate limiting doesn't care which
database backs the accounts), but real Redis for the counters.
"""

import asyncio
import uuid

import pytest
import redis.asyncio as redis_asyncio
from fastapi import HTTPException

from api.config import settings
from api.security import rate_limit as rate_limit_module
from api.security.rate_limit import enforce_rate_limit

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


async def test_account_restore_request_is_rate_limited_by_email(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    await client.delete("/account/me", headers={"Authorization": f"Bearer {access_token}"})

    for _ in range(settings.ACCOUNT_RESTORE_RATE_LIMIT_MAX_ATTEMPTS):
        response = await client.post("/account/restore/request", json={"email": register_payload["email"]})
        assert response.status_code == 200

    blocked = await client.post("/account/restore/request", json={"email": register_payload["email"]})
    assert blocked.status_code == 429


async def test_consent_reactivation_request_is_rate_limited_by_email(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    await client.post("/account/consent/withdraw", headers={"Authorization": f"Bearer {access_token}"})

    for _ in range(settings.ACCOUNT_RESTORE_RATE_LIMIT_MAX_ATTEMPTS):
        response = await client.post("/account/consent/reactivate/request", json={"email": register_payload["email"]})
        assert response.status_code == 200

    blocked = await client.post("/account/consent/reactivate/request", json={"email": register_payload["email"]})
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


async def test_2fa_verify_recovery_code_is_rate_limited_per_mfa_token(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    import pyotp
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)

    login = await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    mfa_token = login.json()["mfa_token"]

    for _ in range(settings.TWO_FA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS):
        response = await client.post("/auth/2fa/verify-recovery-code", json={"mfa_token": mfa_token, "recovery_code": "AAAA-AAAA-AAAA"})
        assert response.status_code == 401  # wrong code, but still under the limit

    blocked = await client.post("/auth/2fa/verify-recovery-code", json={"mfa_token": mfa_token, "recovery_code": "AAAA-AAAA-AAAA"})
    assert blocked.status_code == 429


async def test_2fa_lockout_recovery_request_is_rate_limited_by_email(client, register_payload):
    import pyotp

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)

    for i in range(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS):
        response = await client.post(
            "/auth/2fa/lockout-recovery/request",
            json={"email": register_payload["email"], "password": "wrong-password"},
            headers={"X-Forwarded-For": f"198.51.101.{i + 1}"},  # different IP each time -- isolates the email-scoped limit
        )
        assert response.status_code == 200  # generic response either way, but still under the limit

    blocked = await client.post(
        "/auth/2fa/lockout-recovery/request",
        json={"email": register_payload["email"], "password": "wrong-password"},
        headers={"X-Forwarded-For": "198.51.101.250"},
    )
    assert blocked.status_code == 429


async def test_2fa_code_endpoints_share_a_rate_limit_by_user_id(client, register_payload):
    """/enable, /disable, and /recovery-codes/regenerate all gate on a
    6-digit TOTP code behind nothing but a valid access token -- without
    a limit, a stolen token alone (no physical device) could brute-force
    that code against any of them. They share one counter, keyed by user
    id, so an attacker can't reset their budget by switching endpoints."""
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    import pyotp
    secret = (await client.post("/auth/2fa/setup", headers=auth_header)).json()["secret"]
    enable = await client.post("/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    assert enable.status_code == 200  # attempt 1 of TWO_FA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS

    for _ in range(settings.TWO_FA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS - 1):
        response = await client.post("/auth/2fa/disable", json={"code": "000000"}, headers=auth_header)
        assert response.status_code == 400  # wrong code, but still under the shared limit

    # One more attempt, on a THIRD endpoint, with the CORRECT code -- still blocked.
    blocked = await client.post("/auth/2fa/recovery-codes/regenerate", json={"code": pyotp.TOTP(secret).now()}, headers=auth_header)
    assert blocked.status_code == 429


async def test_rate_limiting_fails_open_when_redis_is_unreachable(monkeypatch):
    """The core design decision (see api/security/rate_limit.py's
    docstring): a Redis outage degrades brute-force protection, it must
    never take down login/register/etc. entirely."""
    broken_client = redis_asyncio.from_url("redis://127.0.0.1:1/0", decode_responses=True, socket_connect_timeout=1)
    monkeypatch.setattr(rate_limit_module, "_redis", broken_client)

    # Must NOT raise, despite Redis being unreachable.
    await rate_limit_module.enforce_rate_limit("ratelimit:test:unreachable", max_attempts=1, window_seconds=60)


async def test_is_redis_reachable_reflects_actual_connectivity(monkeypatch):
    """Backs GET /health/ready (api/main.py) -- the whole point is that
    the degraded-rate-limiting state above is OBSERVABLE, not just
    silently tolerated. Checks both directions: a real Redis reports
    reachable, a broken one reports not."""
    assert await rate_limit_module.is_redis_reachable() is True

    broken_client = redis_asyncio.from_url("redis://127.0.0.1:1/0", decode_responses=True, socket_connect_timeout=1)
    monkeypatch.setattr(rate_limit_module, "_redis", broken_client)
    assert await rate_limit_module.is_redis_reachable() is False


async def test_sliding_window_catches_a_burst_that_a_fixed_window_would_miss():
    """
    The concrete property that makes this a sliding window and not a
    fixed one: 3 attempts spread near a would-be window boundary (~0.5s
    apart) must be caught even though, under a naive fixed-window
    counter (INCR + EXPIRE-on-first-hit, this module's old design), the
    per-key window started by the first attempt (A) would have already
    fully expired and reset by the time the later ones (C, D) land --
    silently discarding A's count and letting B+C+D slip through as if
    they were a fresh burst, well above the stated limit.

    window=3s, max_attempts=2. Timeline: A@t=0, B@t=2.7 (A still
    in-window, allowed, count=2/2), C@t=3.2 (A has now aged out under
    BOTH designs, so this is legitimately allowed, count=2/2 again --
    but a fixed design's key already reset once at t=3.0, so it would
    independently also allow this), D@t=3.25 (B and C are both still
    within the last 3 seconds -- sliding correctly blocks; a fixed
    per-key window freshly started at C would only be at count=2 here
    and would NOT block, which is exactly the bug this design avoids).
    """
    key = f"ratelimit:test:sliding-window-{uuid.uuid4().hex}"

    await enforce_rate_limit(key, max_attempts=2, window_seconds=3)  # A @ t=0
    await asyncio.sleep(2.7)
    await enforce_rate_limit(key, max_attempts=2, window_seconds=3)  # B @ t=2.7 -- A (age 2.7s) still counts
    await asyncio.sleep(0.5)
    await enforce_rate_limit(key, max_attempts=2, window_seconds=3)  # C @ t=3.2 -- A has aged out (3.2s); only B counts
    await asyncio.sleep(0.05)

    with pytest.raises(HTTPException) as exc_info:
        await enforce_rate_limit(key, max_attempts=2, window_seconds=3)  # D @ t=3.25 -- B (0.55s old) and C (0.05s old) both still count
    assert exc_info.value.status_code == 429
