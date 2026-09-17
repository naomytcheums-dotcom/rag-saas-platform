"""
Brute-force / spam protection for the 5 auth endpoints an attacker would
actually want to hammer: login, register, password/forgot,
verify-email/request, 2fa/verify-login. A hand-rolled sliding-window
counter on Redis (sorted sets), not a third-party library
(slowapi/fastapi-limiter) -- the logic is short enough that a buyer
reading this file can verify exactly what it does in a few minutes, and
it sidesteps those libraries' awkward interaction with reading the
request body twice (once for the rate-limit key, once for the Pydantic
model) when limiting by email rather than just by IP.

Sliding window, not fixed window: each call records this attempt's own
timestamp as a member of a Redis sorted set (score = the timestamp),
first dropping any members older than the window. The count is exact
over a truly rolling `window_seconds` -- unlike a fixed-window counter
(INCR + EXPIRE), there's no boundary where 2x the stated limit slips
through by timing requests around a window reset.

Design choice, stated plainly: if Redis is unreachable, enforce_rate_limit
logs a warning and lets the request through (fails OPEN, not closed).
The alternative -- fail closed, blocking all login/register/etc. -- would
turn a Redis outage into a total auth outage, which is a worse failure
mode than temporarily losing brute-force protection. This matches every
other optional-infra dependency in this codebase (Resend, S3): a backing
service being down degrades one specific protection, it doesn't take the
whole app down.

That trade-off only stays a *deliberate* one, not a silent one, if
someone operating this app can actually see it happening -- a warning
log nobody's watching is not the same as visibility. is_redis_reachable()
below backs GET /health/ready (api/main.py), so a degraded rate limiter
shows up as a readiness signal, not just a line in a log file.
"""

import asyncio
import logging
import time
import uuid

import redis.asyncio as redis_asyncio
from fastapi import HTTPException, status

from api.config import settings
from api.security.redis_client import get_or_rebuild

logger = logging.getLogger(__name__)

# Real bug fixed here (2026-09-15, found via live persona-based testing):
# from_url with no socket_connect_timeout/socket_timeout falls back to
# the OS's own TCP connect timeout (tens of seconds) when Redis is
# unreachable -- the exact "fail open" path this module's docstring
# describes as a deliberate trade-off was still real, just far too slow
# to actually be "open" in any practical sense. Confirmed directly: a
# single connection attempt to an unreachable Redis took ~4s in
# isolation, and /auth/register (which also touches geoip.py's own
# separate Redis client below) took 22-59s wall time with Redis down --
# each of the several Redis touches in one request paying that cost
# independently, since the client has no cached "known down" state
# between calls. A short, explicit timeout makes the fail-open path
# fail open fast, matching the intent already documented above.

# Second real bug fixed here (2026-09-15, found via the regression suite
# intermittently failing with "Event loop is closed" in long combined
# runs, never in isolation): a redis.asyncio client's connection pool
# binds its actual socket to whichever event loop is RUNNING the first
# time it's used, not to the loop that was running when from_url() was
# called. A single client built once at import time is safe only as long
# as exactly one event loop ever exists for the life of the process. That
# assumption held for the deployed app (one Uvicorn worker, one loop) but
# not for the test suite: pytest-asyncio's session-scoped loop is one
# loop, but several other test modules bridge into async code via
# asyncio.run() (see api/tasks/*.py's Celery task wrappers), which spins
# up and tears down its OWN separate loop. If this client's underlying
# connection ever got established while one of those throwaway loops was
# current, the connection pool bound itself to that loop -- and the
# moment asyncio.run() closed it, every later call from the real session
# loop raised exactly "Event loop is closed", in whatever unrelated test
# happened to touch this client next. Rebuilding the client whenever the
# running loop has changed since it was last built removes the shared
# state that made one loop's teardown able to break a different loop's
# test.
_redis: redis_asyncio.Redis | None = None
_redis_loop: asyncio.AbstractEventLoop | None = None


def _get_redis() -> redis_asyncio.Redis:
    global _redis, _redis_loop
    _redis, _redis_loop = get_or_rebuild(
        _redis, _redis_loop, settings.RATE_LIMIT_REDIS_URL,
        decode_responses=True, socket_connect_timeout=3.0, socket_timeout=1.0,
    )
    return _redis


async def enforce_rate_limit(key: str, max_attempts: int, window_seconds: int) -> None:
    """
    Raises HTTP 429 (with a Retry-After header) once `key` has been hit
    more than `max_attempts` times within the trailing `window_seconds`
    -- a true sliding window, re-evaluated fresh on every call.

    Call this multiple times with different keys to rate-limit the same
    request along more than one dimension at once (e.g. login is limited
    by IP AND by the target email separately -- see api/routers/auth.py).

    Also logs a WARNING (not just on Redis failure) the moment a limit is
    actually exceeded, naming the key -- the one place in the codebase an
    operator can grep for "is someone actively trying to brute-force
    account X" after the fact. Emitted here, not at each call site, so
    every one of the 5 protected endpoints gets this for free.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    now = time.time()
    window_start = now - window_seconds

    try:
        pipe = _get_redis().pipeline()
        pipe.zremrangebyscore(key, 0, window_start)  # drop attempts that have aged out of the window
        pipe.zadd(key, {str(uuid.uuid4()): now})  # record this attempt (a random member -- the score is what matters)
        pipe.zcard(key)  # how many attempts remain within the window, including this one
        pipe.expire(key, window_seconds)  # let Redis reclaim the key on its own if it's never hit again
        _, _, current_count, _ = await pipe.execute()
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: any Redis failure must fail open, see module docstring
        logger.warning("rate limit check failed for key=%s, allowing the request through: %s", key, exc)
        return

    if current_count > max_attempts:
        logger.warning("rate limit exceeded: key=%s max_attempts=%d window_seconds=%d", key, max_attempts, window_seconds)
        retry_after = await _seconds_until_oldest_entry_expires(key, window_seconds, now)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts, try again in {retry_after} seconds",
            headers={"Retry-After": str(retry_after)},
        )


async def is_redis_reachable() -> bool:
    """Used only by GET /health/ready (api/main.py) to surface, rather
    than silently tolerate, the exact condition enforce_rate_limit()
    above already handles gracefully: Redis being unreachable. Never
    called from enforce_rate_limit() itself -- that path already has its
    own try/except and must not pay for an extra round-trip just to
    decide whether to log."""
    try:
        await _get_redis().ping()
        return True
    except Exception:  # noqa: BLE001 -- any failure means "not reachable," full stop
        return False


async def _seconds_until_oldest_entry_expires(key: str, window_seconds: int, now: float) -> int:
    """How long until the window's oldest still-counted attempt ages out
    (at which point the caller would no longer be over the limit,
    assuming they make no further attempts) -- what the Retry-After
    header promises. Falls back to the full window length if this lookup
    itself fails; a slightly-too-generous Retry-After is harmless."""
    try:
        oldest = await _get_redis().zrange(key, 0, 0, withscores=True)
        if oldest:
            oldest_timestamp = oldest[0][1]
            return max(int(window_seconds - (now - oldest_timestamp)), 1)
    except Exception:  # noqa: BLE001
        pass
    return window_seconds
