"""Hardening Mission, §4/§25 -- a security dependency going down must not
make the application more permissive. With Redis unreachable,
`enforce_rate_limit` used to let EVERYTHING through (unbounded bursts on
every costly endpoint); it now degrades to an in-process sliding window
with the same limits. No Redis needed here: `_get_redis` is forced to fail."""

import uuid

import pytest
from fastapi import HTTPException

from api.config import settings
from api.security import rate_limit as rate_limit_module
from api.security.rate_limit import enforce_rate_limit


@pytest.fixture(autouse=True)
def _redis_is_down(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)

    def _boom():
        raise ConnectionError("simulated Redis outage")

    monkeypatch.setattr(rate_limit_module, "_get_redis", _boom)
    rate_limit_module._local_windows.clear()
    yield
    rate_limit_module._local_windows.clear()


async def test_a_burst_is_still_bounded_while_redis_is_down():
    key = f"ratelimit:test:degraded:{uuid.uuid4().hex}"
    for _ in range(3):
        await enforce_rate_limit(key, max_attempts=3, window_seconds=60)

    with pytest.raises(HTTPException) as exc_info:
        await enforce_rate_limit(key, max_attempts=3, window_seconds=60)

    assert exc_info.value.status_code == 429
    assert 1 <= int(exc_info.value.headers["Retry-After"]) <= 60


async def test_the_in_process_window_slides_and_old_attempts_age_out(monkeypatch):
    key = f"ratelimit:test:degraded-slide:{uuid.uuid4().hex}"
    clock = {"now": 1_000_000.0}
    monkeypatch.setattr(rate_limit_module.time, "time", lambda: clock["now"])

    await enforce_rate_limit(key, max_attempts=1, window_seconds=10)
    with pytest.raises(HTTPException):
        await enforce_rate_limit(key, max_attempts=1, window_seconds=10)

    clock["now"] += 11  # the first attempt is now outside the window
    await enforce_rate_limit(key, max_attempts=1, window_seconds=10)


async def test_keys_are_counted_independently_while_redis_is_down():
    suffix = uuid.uuid4().hex
    await enforce_rate_limit(f"ratelimit:test:a:{suffix}", max_attempts=1, window_seconds=60)
    await enforce_rate_limit(f"ratelimit:test:b:{suffix}", max_attempts=1, window_seconds=60)


async def test_the_in_process_store_is_bounded(monkeypatch):
    monkeypatch.setattr(rate_limit_module, "_LOCAL_MAX_KEYS", 5)
    clock = {"now": 2_000_000.0}
    monkeypatch.setattr(rate_limit_module.time, "time", lambda: clock["now"])

    for i in range(20):
        await enforce_rate_limit(f"ratelimit:test:flood:{i}", max_attempts=5, window_seconds=10)
        clock["now"] += 11  # every earlier key is fully expired by the next call

    assert len(rate_limit_module._local_windows) <= 6
