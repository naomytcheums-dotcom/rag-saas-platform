"""
Audit findings 29/30 -- fast, offline unit tests for
api/security/trusted_ips.py (IP/CIDR allowlist matching) and
api/security/geoip.py (country-tier lookup logic). The real HTTP call to
ipapi.co is stubbed out (same pattern as tests/test_password_strength.py's
HIBP stub) so these stay fast/offline; a real-Redis-backed caching test
lives in tests/test_geo_adaptive_rate_limit_integration.py alongside the
adaptive-rate-limit endpoint tests, matching how
tests/test_rate_limiting_integration.py separates plain rate-limit unit
tests from Redis-dependent ones.
"""

import httpx
import pytest
from fastapi import Request

from api.config import settings
from api.security import geoip
from api.security import trusted_ips as trusted_ips_module
from api.security.trusted_ips import direct_peer_ip, is_trusted_ip


def _fake_request(peer_ip: str | None, forwarded_for: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", forwarded_for.encode())] if forwarded_for else []
    scope = {
        "type": "http",
        "headers": headers,
        "client": (peer_ip, 12345) if peer_ip is not None else None,
    }
    return Request(scope)


# -- trusted_ips.py -----------------------------------------------------

def test_exact_ip_match_is_trusted(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_IPS", "203.0.113.5,198.51.100.9")
    trusted_ips_module._parse_trusted_networks.cache_clear()
    assert is_trusted_ip("203.0.113.5") is True
    assert is_trusted_ip("198.51.100.9") is True


def test_ip_outside_the_allowlist_is_not_trusted(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_IPS", "203.0.113.5")
    trusted_ips_module._parse_trusted_networks.cache_clear()
    assert is_trusted_ip("203.0.113.6") is False


def test_cidr_range_matches_any_address_inside_it(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_IPS", "10.8.0.0/24")
    trusted_ips_module._parse_trusted_networks.cache_clear()
    assert is_trusted_ip("10.8.0.1") is True
    assert is_trusted_ip("10.8.0.254") is True
    assert is_trusted_ip("10.8.1.1") is False  # just outside the /24


def test_empty_allowlist_trusts_nothing(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_IPS", "")
    trusted_ips_module._parse_trusted_networks.cache_clear()
    assert is_trusted_ip("203.0.113.5") is False
    assert is_trusted_ip(None) is False


def test_malformed_entries_in_the_allowlist_are_skipped_not_crashed_on(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_IPS", "not-an-ip, 203.0.113.5 ,,also-garbage")
    trusted_ips_module._parse_trusted_networks.cache_clear()
    assert is_trusted_ip("203.0.113.5") is True  # the one valid entry still works
    assert is_trusted_ip("not-an-ip") is False   # never raises on a bad candidate IP either


def test_unparseable_candidate_ip_is_not_trusted(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_IPS", "203.0.113.5")
    trusted_ips_module._parse_trusted_networks.cache_clear()
    assert is_trusted_ip("this-is-not-an-ip-address") is False


def test_direct_peer_ip_ignores_x_forwarded_for():
    """The security-critical property this module exists for: a caller
    cannot spoof their way into the trusted-IP bypass via a header they
    fully control -- see trusted_ips.py's top docstring."""
    request = _fake_request(peer_ip="198.51.100.99", forwarded_for="203.0.113.5")
    assert direct_peer_ip(request) == "198.51.100.99"


def test_direct_peer_ip_is_none_when_there_is_no_client():
    request = _fake_request(peer_ip=None)
    assert direct_peer_ip(request) is None


# -- geoip.py -------------------------------------------------------------

class _FakeGeoResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://ipapi.co/1.2.3.4/country/")
            raise httpx.HTTPStatusError("error", request=request, response=httpx.Response(self.status_code, request=request))


class _FakeGeoAsyncClient:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url):
        if self._exc is not None:
            raise self._exc
        return self._response


class _FakeRedisForGeoip:
    """A minimal in-memory stand-in for the two Redis calls geoip.py
    actually makes (get/set with an `ex` kwarg) -- keeps these unit tests
    infra-free; the real-Redis round trip is proven separately in
    tests/test_geo_adaptive_rate_limit_integration.py."""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value


@pytest.fixture(autouse=True)
def _fake_redis_for_geoip_module(monkeypatch):
    monkeypatch.setattr(geoip, "_redis", _FakeRedisForGeoip())


async def test_lookup_country_returns_the_code_from_a_successful_response(monkeypatch):
    monkeypatch.setattr(geoip.httpx, "AsyncClient", lambda timeout: _FakeGeoAsyncClient(_FakeGeoResponse("fr\n")))
    assert await geoip.lookup_country("1.2.3.4") == "FR"


async def test_lookup_country_is_none_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "GEO_IP_LOOKUP_ENABLED", False)
    monkeypatch.setattr(geoip.httpx, "AsyncClient", lambda timeout: _FakeGeoAsyncClient(_FakeGeoResponse("FR")))
    assert await geoip.lookup_country("1.2.3.4") is None


async def test_lookup_country_is_none_for_an_empty_ip(monkeypatch):
    assert await geoip.lookup_country(None) is None
    assert await geoip.lookup_country("") is None


async def test_lookup_country_fails_open_on_a_network_error(monkeypatch):
    monkeypatch.setattr(geoip.httpx, "AsyncClient", lambda timeout: _FakeGeoAsyncClient(exc=httpx.ConnectError("refused")))
    assert await geoip.lookup_country("1.2.3.4") is None


async def test_lookup_country_fails_open_on_a_non_200_response(monkeypatch):
    monkeypatch.setattr(geoip.httpx, "AsyncClient", lambda timeout: _FakeGeoAsyncClient(_FakeGeoResponse("", status_code=503)))
    assert await geoip.lookup_country("1.2.3.4") is None


async def test_lookup_country_fails_open_on_a_malformed_body(monkeypatch):
    """ipapi.co returns a plain-text error message (not a 2-letter code)
    for a private/reserved IP, e.g. 'Reserved' -- must not be mistaken
    for a real country code."""
    monkeypatch.setattr(geoip.httpx, "AsyncClient", lambda timeout: _FakeGeoAsyncClient(_FakeGeoResponse("Reserved")))
    assert await geoip.lookup_country("10.0.0.1") is None


async def test_lookup_country_caches_the_result_and_does_not_refetch(monkeypatch):
    call_count = 0

    class _CountingClient(_FakeGeoAsyncClient):
        async def get(self, url):
            nonlocal call_count
            call_count += 1
            return await super().get(url)

    monkeypatch.setattr(geoip.httpx, "AsyncClient", lambda timeout: _CountingClient(_FakeGeoResponse("DE")))

    assert await geoip.lookup_country("5.6.7.8") == "DE"
    assert await geoip.lookup_country("5.6.7.8") == "DE"
    assert call_count == 1  # second call served from the (fake) cache


async def test_lookup_country_caches_an_unknown_result_too(monkeypatch):
    """A negative cache entry ("" stored, not "no entry at all") is still
    a cache hit -- otherwise a country ipapi.co can't resolve would be
    re-fetched on every single request forever."""
    call_count = 0

    class _CountingClient(_FakeGeoAsyncClient):
        async def get(self, url):
            nonlocal call_count
            call_count += 1
            return await super().get(url)

    monkeypatch.setattr(geoip.httpx, "AsyncClient", lambda timeout: _CountingClient(_FakeGeoResponse("Reserved")))

    assert await geoip.lookup_country("10.0.0.1") is None
    assert await geoip.lookup_country("10.0.0.1") is None
    assert call_count == 1


# -- tier_multiplier ------------------------------------------------------

def test_tier_multiplier_is_neutral_with_no_lists_configured(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_COUNTRIES", "")
    monkeypatch.setattr(settings, "SUSPICIOUS_COUNTRIES", "")
    assert geoip.tier_multiplier("FR") == 1.0
    assert geoip.tier_multiplier(None) == 1.0


def test_tier_multiplier_loosens_for_a_trusted_country(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_COUNTRIES", "FR,DE")
    monkeypatch.setattr(settings, "SUSPICIOUS_COUNTRIES", "")
    monkeypatch.setattr(settings, "GEO_RATE_LIMIT_TRUSTED_MULTIPLIER", 2.0)
    assert geoip.tier_multiplier("FR") == 2.0
    assert geoip.tier_multiplier("de") == 2.0  # case-insensitive


def test_tier_multiplier_tightens_for_a_suspicious_country(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_COUNTRIES", "")
    monkeypatch.setattr(settings, "SUSPICIOUS_COUNTRIES", "XX")
    monkeypatch.setattr(settings, "GEO_RATE_LIMIT_SUSPICIOUS_MULTIPLIER", 0.5)
    assert geoip.tier_multiplier("XX") == 0.5


def test_tier_multiplier_prefers_suspicious_when_a_country_is_in_both_lists(monkeypatch):
    """A misconfiguration (the same country listed as both trusted and
    suspicious) resolves to the SAFER outcome -- tighter, not looser."""
    monkeypatch.setattr(settings, "TRUSTED_COUNTRIES", "XX")
    monkeypatch.setattr(settings, "SUSPICIOUS_COUNTRIES", "XX")
    monkeypatch.setattr(settings, "GEO_RATE_LIMIT_SUSPICIOUS_MULTIPLIER", 0.5)
    monkeypatch.setattr(settings, "GEO_RATE_LIMIT_TRUSTED_MULTIPLIER", 2.0)
    assert geoip.tier_multiplier("XX") == 0.5
