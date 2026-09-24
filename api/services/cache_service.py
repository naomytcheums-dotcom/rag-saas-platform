"""
Phase 5, Étape 13 -- Performance: a real, generic, reusable
application-level cache, closing the gap this codebase's own earlier
audit (Étape 8) traced as "Cache Redis applicatif (P3)": until now,
every real Redis usage in api/ was single-purpose (Celery broker/result
backend, rate-limit counters, pub/sub for SSE) -- nothing cached a
query result, a resolved config, or a permission check.

Same fail-open philosophy as api/security/rate_limit.py, for the same
reason: a cache is an optimization, not a source of truth. If Redis is
unreachable, `get_or_set` just calls `loader` directly every time --
slower, never wrong, never a 500. Reuses api/security/redis_client.py's
`get_or_rebuild` (the same loop-rebind fix rate_limit.py/geoip.py/
webauthn.py already needed) rather than hand-rolling a fourth copy of
that logic.

Deliberately NOT a decorator (`@cached(...)`) as illustrated in this
étape's own spec pseudocode -- every real call site in this codebase
already passes a live `AsyncSession`, and a decorator would need to
either thread that session through kwarg-inspection (fragile) or open
its own session (breaks "the caller decides the transaction boundary",
this codebase's own convention, see organization_settings.py's
update_org_settings docstring). `get_or_set(key, loader)` composes with
an already-open session with no magic.

Values are JSON-encoded, not pickled -- same reasoning as every other
JSON column in this codebase's own models: a value that came from
Redis must never deserialize into an arbitrary Python object.
"""

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import redis.asyncio as redis_asyncio

from api.config import settings
from api.security.redis_client import get_or_rebuild

logger = logging.getLogger(__name__)

_redis: redis_asyncio.Redis | None = None
_redis_loop: asyncio.AbstractEventLoop | None = None


def _get_redis() -> redis_asyncio.Redis:
    global _redis, _redis_loop
    _redis, _redis_loop = get_or_rebuild(
        _redis, _redis_loop, settings.CACHE_REDIS_URL,
        decode_responses=True, socket_connect_timeout=3.0, socket_timeout=1.0,
    )
    return _redis


async def get_or_set(key: str, loader: Callable[[], Awaitable[Any]], *, ttl_seconds: int) -> Any:
    """
    Returns the cached value at `key` if present; otherwise calls
    `loader()`, caches its result for `ttl_seconds`, and returns it.

    `loader` is only ever called on a real cache miss (or when caching
    is disabled/unreachable) -- never speculatively -- so it's safe to
    pass an async function that does a real DB query.
    """
    if not settings.APP_CACHE_ENABLED:
        return await loader()

    try:
        cached = await _get_redis().get(key)
        if cached is not None:
            return json.loads(cached)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: any Redis failure must fail open, same as rate_limit.py
        logger.warning("cache read failed for key=%s, falling back to loader: %s", key, exc)
        return await loader()

    value = await loader()
    try:
        await _get_redis().set(key, json.dumps(value), ex=ttl_seconds)
    except Exception as exc:  # noqa: BLE001 -- a failed cache WRITE must not fail the caller's real request
        logger.warning("cache write failed for key=%s, value was still computed and returned: %s", key, exc)
    return value


async def invalidate(key: str) -> None:
    """Called by the same write path that just changed the underlying
    row (e.g. update_org_settings) -- deleting rather than updating in
    place, so the next real read repopulates from the actual DB rather
    than trusting the writer to have re-serialized the effective value
    correctly."""
    if not settings.APP_CACHE_ENABLED:
        return
    try:
        await _get_redis().delete(key)
    except Exception as exc:  # noqa: BLE001 -- same fail-open reasoning as get_or_set
        logger.warning("cache invalidation failed for key=%s (a stale value may be served until ttl_seconds expires): %s", key, exc)


async def is_redis_reachable() -> bool:
    """Same purpose as rate_limit.py's own is_redis_reachable() -- backs
    GET /health/ready so a degraded cache is a visible readiness signal,
    not just a warning log nobody's watching."""
    try:
        await _get_redis().ping()
        return True
    except Exception:  # noqa: BLE001 -- readiness probe: any failure means "not reachable", the exact reason doesn't matter here
        return False
