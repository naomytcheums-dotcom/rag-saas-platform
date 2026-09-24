"""
Phase 5, Étape 13 -- api/services/cache_service.py, tested against a
REAL Redis, same convention as tests/test_rate_limiting_integration.py
(its own module docstring explains why: this suite's autouse fixture
disables APP_CACHE_ENABLED for every other test file, so this file
explicitly re-enables it and skips cleanly if no real Redis is reachable
rather than mocking one).
"""

import uuid

import pytest
import redis.asyncio as redis_asyncio

from api.config import settings
from api.services import cache_service

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture(autouse=True)
async def _enable_app_cache(monkeypatch):
    monkeypatch.setattr(settings, "APP_CACHE_ENABLED", True)
    try:
        async with redis_asyncio.from_url(settings.CACHE_REDIS_URL, decode_responses=True) as r:
            await r.ping()
            # CACHE_REDIS_URL has its own dedicated Redis DB number (see
            # api/config.py's comment) -- a full flush here is safe, same
            # reasoning as the rate-limiting integration tests' own fixture.
            await r.flushdb()
    except Exception as exc:
        pytest.skip(f"Redis is not reachable at CACHE_REDIS_URL -- skipping cache tests ({exc})")


async def test_get_or_set_calls_loader_once_on_repeated_calls():
    key = f"test:{uuid.uuid4()}"
    calls = []

    async def loader():
        calls.append(1)
        return {"value": 42}

    first = await cache_service.get_or_set(key, loader, ttl_seconds=60)
    second = await cache_service.get_or_set(key, loader, ttl_seconds=60)

    assert first == {"value": 42}
    assert second == {"value": 42}
    assert len(calls) == 1  # second call was a real cache hit, loader not re-invoked


async def test_invalidate_forces_the_next_call_to_reload():
    key = f"test:{uuid.uuid4()}"
    calls = []

    async def loader():
        calls.append(1)
        return len(calls)

    first = await cache_service.get_or_set(key, loader, ttl_seconds=60)
    await cache_service.invalidate(key)
    second = await cache_service.get_or_set(key, loader, ttl_seconds=60)

    assert first == 1
    assert second == 2  # loader ran again after invalidation, not served stale
    assert len(calls) == 2


async def test_get_or_set_falls_back_to_loader_when_caching_disabled(monkeypatch):
    monkeypatch.setattr(settings, "APP_CACHE_ENABLED", False)
    key = f"test:{uuid.uuid4()}"
    calls = []

    async def loader():
        calls.append(1)
        return len(calls)

    first = await cache_service.get_or_set(key, loader, ttl_seconds=60)
    second = await cache_service.get_or_set(key, loader, ttl_seconds=60)

    assert first == 1
    assert second == 2  # disabled: every call is a real passthrough, never cached
    assert len(calls) == 2


async def test_is_redis_reachable_is_true_against_the_real_test_redis():
    assert await cache_service.is_redis_reachable() is True
