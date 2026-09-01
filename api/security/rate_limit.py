"""
Brute-force / spam protection for the 5 auth endpoints an attacker would
actually want to hammer: login, register, password/forgot,
verify-email/request, 2fa/verify-login. A hand-rolled fixed-window
counter on Redis, not a third-party library (slowapi/fastapi-limiter) --
the logic is short enough that a buyer reading this file can verify
exactly what it does in under a minute, and it sidesteps those libraries'
awkward interaction with reading the request body twice (once for the
rate-limit key, once for the Pydantic model) when limiting by email
rather than just by IP.

Design choice, stated plainly: if Redis is unreachable, enforce_rate_limit
logs a warning and lets the request through (fails OPEN, not closed).
The alternative -- fail closed, blocking all login/register/etc. -- would
turn a Redis outage into a total auth outage, which is a worse failure
mode than temporarily losing brute-force protection. This matches every
other optional-infra dependency in this codebase (Resend, S3): a backing
service being down degrades one specific protection, it doesn't take the
whole app down.
"""

import logging

import redis.asyncio as redis_asyncio
from fastapi import HTTPException, status

from api.config import settings

logger = logging.getLogger(__name__)

_redis = redis_asyncio.from_url(settings.RATE_LIMIT_REDIS_URL, decode_responses=True)


async def enforce_rate_limit(key: str, max_attempts: int, window_seconds: int) -> None:
    """
    Raises HTTP 429 (with a Retry-After header) once `key` has been hit
    more than `max_attempts` times within a rolling `window_seconds`
    window. Fixed-window counting (INCR + EXPIRE-on-first-hit), not a
    sliding log -- simpler, one round trip per call, and "up to 2x the
    stated limit at a window boundary" is an acceptable trade-off for
    this use case (it's brute-force protection, not billing).

    Call this multiple times with different keys to rate-limit the same
    request along more than one dimension at once (e.g. login is limited
    by IP AND by the target email separately -- see api/routers/auth.py).
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    try:
        current = await _redis.incr(key)
        if current == 1:
            await _redis.expire(key, window_seconds)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: any Redis failure must fail open, see module docstring
        logger.warning("rate limit check failed for key=%s, allowing the request through: %s", key, exc)
        return

    if current > max_attempts:
        try:
            ttl = await _redis.ttl(key)
        except Exception:  # noqa: BLE001
            ttl = window_seconds
        retry_after = max(ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts, try again in {retry_after} seconds",
            headers={"Retry-After": str(retry_after)},
        )
