"""Partie 5.1.6 -- retry mechanism. Real asyncio.sleep/time.sleep are
patched to instant no-ops so backoff delays don't slow this fast suite
down -- the backoff CALCULATION itself (calculate_backoff) is tested
against real, unpatched arithmetic."""

import pytest

from api.services.retry import calculate_backoff, retry_async, retry_sync, should_retry, with_retry, with_retry_sync


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", lambda *_a, **_k: _instant())
    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)


async def _instant():
    return None


# --------------------------------------- calculate_backoff --


def test_calculate_backoff_grows_exponentially():
    assert calculate_backoff(0, base_delay=1.0, backoff_factor=2.0, max_delay=100.0) == 1.0
    assert calculate_backoff(1, base_delay=1.0, backoff_factor=2.0, max_delay=100.0) == 2.0
    assert calculate_backoff(2, base_delay=1.0, backoff_factor=2.0, max_delay=100.0) == 4.0


def test_calculate_backoff_is_capped_at_max_delay():
    assert calculate_backoff(10, base_delay=1.0, backoff_factor=2.0, max_delay=5.0) == 5.0


# --------------------------------------- should_retry --


def test_should_retry_matches_a_configured_exception_type():
    assert should_retry(ValueError("x"), (ValueError, TypeError)) is True
    assert should_retry(KeyError("x"), (ValueError, TypeError)) is False


# --------------------------------------- retry_async --


async def test_retry_async_succeeds_on_the_real_first_try():
    async def _ok():
        return "done"

    assert await retry_async(_ok) == "done"


async def test_retry_async_retries_and_eventually_succeeds():
    """Validation criterion: le retry fonctionne."""
    calls = {"count": 0}

    async def _flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise ValueError("not yet")
        return "recovered"

    result = await retry_async(_flaky, max_attempts=5)
    assert result == "recovered"
    assert calls["count"] == 3


async def test_retry_async_raises_the_real_last_exception_after_exhausting_attempts():
    """Validation criterion: les tentatives sont limitées."""
    calls = {"count": 0}

    async def _always_fails():
        calls["count"] += 1
        raise ValueError(f"attempt {calls['count']}")

    with pytest.raises(ValueError, match="attempt 3"):
        await retry_async(_always_fails, max_attempts=3)
    assert calls["count"] == 3


async def test_retry_async_does_not_retry_an_unconfigured_exception_type():
    """Validation criterion: les exceptions sont gérées (seules celles
    demandées sont retentées)."""
    calls = {"count": 0}

    async def _fails_with_key_error():
        calls["count"] += 1
        raise KeyError("nope")

    with pytest.raises(KeyError):
        await retry_async(_fails_with_key_error, max_attempts=5, retry_on_exceptions=(ValueError,))
    assert calls["count"] == 1


# --------------------------------------- retry_sync --


def test_retry_sync_retries_and_eventually_succeeds():
    calls = {"count": 0}

    def _flaky():
        calls["count"] += 1
        if calls["count"] < 2:
            raise ValueError("not yet")
        return "recovered"

    assert retry_sync(_flaky, max_attempts=3) == "recovered"


# --------------------------------------- decorators --


async def test_with_retry_decorator_retries_a_real_async_function():
    calls = {"count": 0}

    @with_retry(max_attempts=3)
    async def _flaky():
        calls["count"] += 1
        if calls["count"] < 2:
            raise ValueError("not yet")
        return "ok"

    assert await _flaky() == "ok"


def test_with_retry_sync_decorator_retries_a_real_sync_function():
    calls = {"count": 0}

    @with_retry_sync(max_attempts=3)
    def _flaky():
        calls["count"] += 1
        if calls["count"] < 2:
            raise ValueError("not yet")
        return "ok"

    assert _flaky() == "ok"
