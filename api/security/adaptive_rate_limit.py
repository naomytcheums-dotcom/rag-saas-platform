"""
Audit findings 29/30: the geo/trust-aware wrapper around
api/security/rate_limit.py's enforce_rate_limit(), used by the two
IP-scoped brute-force checks (login, register) instead of calling
enforce_rate_limit() directly. Email-scoped limits (login's second check,
password/forgot, 2FA) are untouched -- an email address has no
geography, so neither adjustment applies to them.
"""

import logging
import math

from fastapi import Request

from api.config import settings
from api.security.geoip import lookup_country, tier_multiplier
from api.security.rate_limit import enforce_rate_limit
from api.security.trusted_ips import direct_peer_ip, is_trusted_ip
from api.utils import client_ip

logger = logging.getLogger(__name__)


async def enforce_adaptive_rate_limit(request: Request, key: str, base_max_attempts: int, window_seconds: int) -> None:
    """
    Two independent adjustments, checked in this order:

    1. TRUSTED_IPS allowlist (item 30) -- an exact IP or CIDR match skips
       rate limiting for this call ENTIRELY, with no Redis round trip at
       all. Checked against the real TCP peer address
       (trusted_ips.direct_peer_ip), never the spoofable
       X-Forwarded-For-preferring client_ip() -- see trusted_ips.py's
       own docstring for why that distinction is load-bearing for an
       outright bypass specifically.

    2. Country-tier multiplier (item 29) -- a caller whose IP resolves to
       a TRUSTED_COUNTRIES entry gets base_max_attempts multiplied by
       GEO_RATE_LIMIT_TRUSTED_MULTIPLIER (a LOOSER limit);
       SUSPICIOUS_COUNTRIES multiplies by GEO_RATE_LIMIT_SUSPICIOUS_MULTIPLIER
       (a STRICTER one). Rounded up and floored at 1 so a fractional
       multiplier can never produce "0 attempts allowed, forever
       blocked." Uses client_ip() here -- unlike the allowlist above,
       this only shifts a limit up or down, the same trust level every
       other per-IP rate-limit key in this codebase already operates at,
       not an outright bypass.

    Both a geoip lookup failure and an unset TRUSTED_COUNTRIES/
    SUSPICIOUS_COUNTRIES resolve to multiplier 1.0 -- identical behavior
    to calling enforce_rate_limit() directly, so this is a safe drop-in
    replacement with no functional change until those settings are
    actually configured.

    RATE_LIMIT_ENABLED is checked FIRST, before any of the above --
    mirroring enforce_rate_limit()'s own first line -- so disabling rate
    limiting also fully disables the trusted-IP/geoip machinery around
    it, with zero Redis or network calls. This matters beyond symmetry:
    tests/conftest.py's autouse fixture sets RATE_LIMIT_ENABLED=False
    specifically so the fast SQLite suite needs neither Redis nor
    outbound internet access -- calling is_trusted_ip()/lookup_country()
    before this check would silently reintroduce both dependencies into
    every one of that suite's ~150+ calls to /auth/login and
    /auth/register, exactly the failure mode this early return exists to
    prevent.
    """
    if not settings.RATE_LIMIT_ENABLED:
        await enforce_rate_limit(key, base_max_attempts, window_seconds)  # no-op; delegated so both functions agree on "disabled" in exactly one place
        return

    if is_trusted_ip(direct_peer_ip(request)):
        return

    ip = client_ip(request)
    country = await lookup_country(ip)
    multiplier = tier_multiplier(country)
    adjusted_max_attempts = max(1, math.ceil(base_max_attempts * multiplier))
    if adjusted_max_attempts != base_max_attempts:
        logger.info(
            "adaptive rate limit: key=%s country=%s multiplier=%.2f base=%d adjusted=%d",
            key, country, multiplier, base_max_attempts, adjusted_max_attempts,
        )
    await enforce_rate_limit(key, adjusted_max_attempts, window_seconds)
