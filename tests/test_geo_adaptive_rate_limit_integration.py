"""
Audit findings 29/30, tested against REAL Redis -- same reasoning and
same _enable_rate_limiting fixture pattern as
tests/test_rate_limiting_integration.py (rate limiting is OFF by default
for the rest of the suite, see tests/conftest.py).

httpx's ASGITransport (used by the `client` fixture, see conftest.py)
gives every request the same fixed TCP peer address, 127.0.0.1 -- proven
useful here rather than worked around: it's exactly what makes the
TRUSTED_IPS bypass test able to assert against a known, stable
direct_peer_ip() without needing a real second network interface.

The geoip.py module keeps its OWN Redis connection (its own module-level
`_redis`, not api/security/rate_limit.py's -- see that module's
docstring for why) -- NOT monkeypatched anywhere in this file, unlike
tests/test_trusted_ips_and_geoip.py's fake-redis unit tests, so the
caching test below exercises the real Redis round trip end to end.
"""

import uuid

import redis.asyncio as redis_asyncio
import pytest

from api.config import settings
from api.security import adaptive_rate_limit as adaptive_rate_limit_module
from api.security import geoip as geoip_module
from api.security import trusted_ips as trusted_ips_module

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture(autouse=True)
async def _enable_rate_limiting(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "TRUSTED_IPS", "")
    monkeypatch.setattr(settings, "TRUSTED_COUNTRIES", "")
    monkeypatch.setattr(settings, "SUSPICIOUS_COUNTRIES", "")
    trusted_ips_module._parse_trusted_networks.cache_clear()
    try:
        async with redis_asyncio.from_url(settings.RATE_LIMIT_REDIS_URL, decode_responses=True) as r:
            await r.ping()
            await r.flushdb()  # same dedicated DB as test_rate_limiting_integration.py, safe to flush -- see that file's comment
    except Exception as exc:
        pytest.skip(f"Redis is not reachable at RATE_LIMIT_REDIS_URL -- skipping geo/trusted-IP rate limiting tests ({exc})")


def _unique_register_payload():
    return {
        "email": f"geo-adaptive-{uuid.uuid4().hex[:10]}@example.com",
        "password": "correct-horse-battery-staple",
        "accept_terms": True,
    }


async def _register_n_times(client, count, headers=None):
    """POST /auth/register is rate-limited by IP ONLY (no email-scoped
    second counter, unlike /auth/login) -- exactly the single-dimension
    target these tests need to isolate the IP-adaptive behavior under
    test. A fresh, unique email each call so account-already-exists
    (409) can never masquerade as "not yet rate-limited\" (200/201)."""
    statuses = []
    for _ in range(count):
        response = await client.post("/auth/register", json=_unique_register_payload(), headers=headers or {})
        statuses.append(response.status_code)
    return statuses


async def test_trusted_ip_bypasses_rate_limiting_entirely(monkeypatch, client):
    """httpx's ASGITransport always reports 127.0.0.1 as the direct TCP
    peer (see this file's docstring) -- allowlisting exactly that lets
    this test hammer /auth/register well past
    REGISTER_RATE_LIMIT_MAX_ATTEMPTS and still never get a 429."""
    monkeypatch.setattr(settings, "TRUSTED_IPS", "127.0.0.1")
    trusted_ips_module._parse_trusted_networks.cache_clear()

    statuses = await _register_n_times(client, settings.REGISTER_RATE_LIMIT_MAX_ATTEMPTS + 5)
    assert all(status == 201 for status in statuses)  # never 429


async def test_spoofing_x_forwarded_for_does_not_grant_the_trusted_ip_bypass(monkeypatch, client):
    """The actual vulnerability this feature could have introduced: an
    allowlist checked against the spoofable X-Forwarded-For header would
    let ANY anonymous caller bypass rate limiting by just claiming to be
    a trusted IP. Confirms it does NOT -- direct_peer_ip() (127.0.0.1 for
    every ASGITransport request) is what's actually checked, so setting
    TRUSTED_IPS to a value that only matches a SPOOFED X-Forwarded-For
    must not exempt this caller."""
    monkeypatch.setattr(settings, "TRUSTED_IPS", "203.0.113.5")  # NOT 127.0.0.1
    trusted_ips_module._parse_trusted_networks.cache_clear()
    # This test is about the allowlist's anti-spoofing property, not
    # geoip -- since is_trusted_ip() correctly returns False here,
    # enforce_adaptive_rate_limit falls through to a REAL lookup_country()
    # call otherwise, hitting the live (rate-limited, free-tier) ipapi.co
    # once per register attempt for no reason this test cares about.
    # Under a long combined test run that repeatedly exercises this same
    # code path across many files, that real dependency intermittently
    # 429s or times out -- observed directly in CI-scale runs (ipapi.co
    # itself returning 429, plus a stale connection surfacing as "Event
    # loop is closed"), which only matters here because of Redis's
    # deliberate fail-open behavior (api/security/rate_limit.py) letting
    # the very request under test through. Stubbed the same way the
    # country-tier tests below already stub it, for a reason specific to
    # THIS test: determinism, not behavior under test.
    async def _fake_lookup_country(ip):
        return None

    monkeypatch.setattr(adaptive_rate_limit_module, "lookup_country", _fake_lookup_country)
    headers = {"X-Forwarded-For": "203.0.113.5"}  # attacker claims to be the trusted IP

    statuses = await _register_n_times(client, settings.REGISTER_RATE_LIMIT_MAX_ATTEMPTS + 1, headers=headers)
    assert statuses[-1] == 429  # NOT bypassed


async def test_trusted_country_widens_the_effective_register_limit(monkeypatch, client):
    monkeypatch.setattr(settings, "TRUSTED_COUNTRIES", "FR")
    monkeypatch.setattr(settings, "GEO_RATE_LIMIT_TRUSTED_MULTIPLIER", 2.0)

    async def _fake_lookup_country(ip):
        return "FR"

    monkeypatch.setattr(adaptive_rate_limit_module, "lookup_country", _fake_lookup_country)

    # base limit doubled -> allowed up to 2x REGISTER_RATE_LIMIT_MAX_ATTEMPTS.
    doubled_limit = settings.REGISTER_RATE_LIMIT_MAX_ATTEMPTS * 2
    statuses = await _register_n_times(client, doubled_limit + 1)
    assert all(status == 201 for status in statuses[:doubled_limit])
    assert statuses[-1] == 429  # eventually still blocked, just at a higher threshold


async def test_suspicious_country_tightens_the_effective_register_limit(monkeypatch, client):
    monkeypatch.setattr(settings, "SUSPICIOUS_COUNTRIES", "XX")
    monkeypatch.setattr(settings, "GEO_RATE_LIMIT_SUSPICIOUS_MULTIPLIER", 0.5)

    async def _fake_lookup_country(ip):
        return "XX"

    monkeypatch.setattr(adaptive_rate_limit_module, "lookup_country", _fake_lookup_country)

    reduced_limit = -(-settings.REGISTER_RATE_LIMIT_MAX_ATTEMPTS // 2)  # ceil division, matches enforce_adaptive_rate_limit's math.ceil
    statuses = await _register_n_times(client, reduced_limit + 1)
    assert all(status == 201 for status in statuses[:reduced_limit])
    assert statuses[-1] == 429


async def test_a_geoip_lookup_failure_falls_back_to_the_unadjusted_limit(monkeypatch, client):
    """geoip.py fails open (returns None) on any lookup failure -- proven
    end to end here rather than just at the unit level: even with
    TRUSTED_COUNTRIES configured, a country lookup that can't resolve
    must behave exactly like the feature was never enabled."""
    monkeypatch.setattr(settings, "TRUSTED_COUNTRIES", "FR")

    async def _failing_lookup_country(ip):
        return None

    monkeypatch.setattr(adaptive_rate_limit_module, "lookup_country", _failing_lookup_country)

    statuses = await _register_n_times(client, settings.REGISTER_RATE_LIMIT_MAX_ATTEMPTS + 1)
    assert statuses[-1] == 429  # unadjusted limit, not doubled


async def test_geoip_country_lookup_is_actually_cached_in_real_redis(monkeypatch):
    """Unlike tests/test_trusted_ips_and_geoip.py's fake-redis unit test
    of the same property, this exercises geoip.py's real module-level
    Redis client (see this file's top docstring) -- proves the caching
    contract holds against actual infrastructure, not just the Python
    logic around it."""
    call_count = 0

    async def _counting_fetch(ip):
        nonlocal call_count
        call_count += 1
        return "DE"

    monkeypatch.setattr(geoip_module, "_fetch_country_from_api", _counting_fetch)
    ip = f"198.51.100.{uuid.uuid4().int % 250 + 1}"  # a fresh, never-before-cached IP for this test

    assert await geoip_module.lookup_country(ip) == "DE"
    assert await geoip_module.lookup_country(ip) == "DE"
    assert call_count == 1
