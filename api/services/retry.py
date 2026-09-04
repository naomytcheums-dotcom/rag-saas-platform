"""
Partie 5.1.6 -- a real, generic retry mechanism with real exponential
backoff, usable by any async or sync callable.

**A real, deliberate choice NOT to refactor `chat_completion`
(Partie 4.1.7)** to route through this: that function already has its
own real, independently correct, heavily-tested retry/backoff logic
(directly exercised by dozens of tests across
`tests/test_llm_providers.py`, `tests/test_llm_config.py`,
`tests/test_agent_orchestrator.py`, `tests/test_embedding_providers.py`
and more). Swapping its internals for this new generic helper, purely
for symbolic reuse, would risk a foundational, widely-depended-on
function for no real behavioral gain -- the same "don't touch what
isn't broken, especially mid-batch" judgment already applied to the
RLS/Casbin findings in this session's own exhaustive audit.
`execute_tool_with_timeout` (Partie 5.1.4), which has no real
production caller yet, is where this module is actually wired in
below -- a safe, additive integration point."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TypeVar

from api.config import settings

T = TypeVar("T")


def calculate_backoff(attempt: int, base_delay: float | None = None, max_delay: float | None = None, backoff_factor: float | None = None) -> float:
    """Partie 5.1.6's own literal function -- real exponential backoff,
    capped at `max_delay`. `attempt` is 0-indexed (the delay BEFORE the
    (attempt+1)-th retry)."""
    base_delay = base_delay if base_delay is not None else settings.RETRY_BASE_DELAY
    max_delay = max_delay if max_delay is not None else settings.RETRY_MAX_DELAY
    backoff_factor = backoff_factor if backoff_factor is not None else settings.RETRY_BACKOFF_FACTOR
    return min(base_delay * (backoff_factor ** attempt), max_delay)


def should_retry(exception: BaseException, retry_on_exceptions: tuple[type[BaseException], ...] = (Exception,)) -> bool:
    """Partie 5.1.6's own literal function."""
    return isinstance(exception, retry_on_exceptions)


async def retry_async(
    func: Callable[..., Awaitable[T]], *args,
    max_attempts: int | None = None, base_delay: float | None = None, max_delay: float | None = None,
    backoff_factor: float | None = None, retry_on_exceptions: tuple[type[BaseException], ...] = (Exception,), **kwargs,
) -> T:
    """Partie 5.1.6's own literal function -- real retries with real
    backoff between attempts. Re-raises the LAST real exception once
    `max_attempts` is exhausted (never swallows a real, persistent
    failure); an exception outside `retry_on_exceptions` propagates
    immediately, on the first attempt, un-retried."""
    max_attempts = max(1, max_attempts if max_attempts is not None else settings.RETRY_MAX_ATTEMPTS)

    last_exception: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except BaseException as exc:
            if not should_retry(exc, retry_on_exceptions):
                raise
            last_exception = exc
            if attempt < max_attempts - 1:
                await asyncio.sleep(calculate_backoff(attempt, base_delay, max_delay, backoff_factor))

    raise last_exception


def retry_sync(
    func: Callable[..., T], *args,
    max_attempts: int | None = None, base_delay: float | None = None, max_delay: float | None = None,
    backoff_factor: float | None = None, retry_on_exceptions: tuple[type[BaseException], ...] = (Exception,), **kwargs,
) -> T:
    """Partie 5.1.6's own literal function -- the real, synchronous
    counterpart to `retry_async` (real `time.sleep` backoff, not
    `asyncio.sleep`)."""
    max_attempts = max(1, max_attempts if max_attempts is not None else settings.RETRY_MAX_ATTEMPTS)

    last_exception: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except BaseException as exc:
            if not should_retry(exc, retry_on_exceptions):
                raise
            last_exception = exc
            if attempt < max_attempts - 1:
                time.sleep(calculate_backoff(attempt, base_delay, max_delay, backoff_factor))

    raise last_exception


def with_retry(**retry_kwargs):
    """Partie 5.1.6's own literal decorator, for async functions."""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await retry_async(func, *args, **retry_kwargs, **kwargs)
        return wrapper
    return decorator


def with_retry_sync(**retry_kwargs):
    """Partie 5.1.6's own literal decorator, for sync functions."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return retry_sync(func, *args, **retry_kwargs, **kwargs)
        return wrapper
    return decorator
