"""
Audit finding 29: country-tier lookup backing
api/security/adaptive_rate_limit.py -- a caller whose IP resolves to a
TRUSTED_COUNTRIES entry gets a LOOSER effective rate limit; one resolving
to SUSPICIOUS_COUNTRIES gets a STRICTER one, instead of every caller
sharing the same flat LOGIN_RATE_LIMIT_MAX_ATTEMPTS regardless of origin.

ipapi.co (a free, keyless IP-geolocation API) fronted by a Redis cache,
one real lookup per IP per GEO_IP_CACHE_TTL_SECONDS -- without the cache,
a brute-force burst hammering /auth/login from one IP would cost one
outbound HTTP round trip PER LOGIN ATTEMPT, adding real latency to (and a
new external dependency inside) the very rate limit this exists to
adjust. Its own Redis connection, not api/security/rate_limit.py's
(same RATE_LIMIT_REDIS_URL, distinct `geoip:` key prefix) -- reusing that
module's private client would create an import cycle, since
rate_limit.py has no reason to know about geoip at all; only
api/security/adaptive_rate_limit.py needs both.

Fails open -- returns None ("no tier information," i.e. the flat
default) -- on ANY failure: unreachable API, timeout, non-2xx, a
malformed body, or GEO_IP_LOOKUP_ENABLED=False. Same fail-open philosophy
as api/security/rate_limit.py itself (see that module's docstring): a
third-party geolocation API being flaky must degrade to "flat limit for
everyone," never to "nobody can log in."
"""

import logging

import httpx
import redis.asyncio as redis_asyncio

from api.config import settings

logger = logging.getLogger(__name__)

_redis = redis_asyncio.from_url(settings.RATE_LIMIT_REDIS_URL, decode_responses=True)
_CACHE_KEY_PREFIX = "geoip:country:"


async def lookup_country(ip: str | None) -> str | None:
    """Returns an uppercase ISO 3166-1 alpha-2 country code for `ip`, or
    None if unknown/unavailable/disabled. Cached in Redis so repeated
    calls for the same IP within GEO_IP_CACHE_TTL_SECONDS never re-hit
    the network."""
    if not settings.GEO_IP_LOOKUP_ENABLED or not ip:
        return None

    cache_key = f"{_CACHE_KEY_PREFIX}{ip}"
    try:
        cached = await _redis.get(cache_key)
        if cached is not None:
            return cached or None  # "" cached = "looked up before, unknown" -- still a cache hit, no re-fetch
    except Exception as exc:  # noqa: BLE001 -- Redis being down must not block the lookup, just skip the cache
        logger.warning("geoip cache read failed for ip=%s: %s", ip, exc)

    country = await _fetch_country_from_api(ip)

    try:
        await _redis.set(cache_key, country or "", ex=settings.GEO_IP_CACHE_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001
        logger.warning("geoip cache write failed for ip=%s: %s", ip, exc)

    return country


async def _fetch_country_from_api(ip: str) -> str | None:
    url = settings.GEO_IP_API_URL.format(ip=ip)
    try:
        async with httpx.AsyncClient(timeout=settings.GEO_IP_LOOKUP_TIMEOUT_SECONDS) as http_client:
            response = await http_client.get(url)
        response.raise_for_status()
        code = response.text.strip().upper()
        return code if len(code) == 2 and code.isalpha() else None
    except Exception as exc:  # noqa: BLE001 -- any failure (timeout, DNS, non-2xx, garbage body) means "unknown," never a crash
        logger.warning("geoip lookup failed for ip=%s: %s", ip, exc)
        return None


def tier_multiplier(country: str | None) -> float:
    """1.0 (no adjustment) unless `country` is explicitly listed in
    TRUSTED_COUNTRIES or SUSPICIOUS_COUNTRIES -- checked in that order
    against SUSPICIOUS first, so a country accidentally listed in both
    (a misconfiguration) is treated as suspicious, the safer default."""
    if not country:
        return 1.0
    country = country.strip().upper()
    suspicious = {c.strip().upper() for c in settings.SUSPICIOUS_COUNTRIES.split(",") if c.strip()}
    if country in suspicious:
        return settings.GEO_RATE_LIMIT_SUSPICIOUS_MULTIPLIER
    trusted = {c.strip().upper() for c in settings.TRUSTED_COUNTRIES.split(",") if c.strip()}
    if country in trusted:
        return settings.GEO_RATE_LIMIT_TRUSTED_MULTIPLIER
    return 1.0
