"""
A dead Celery broker/result backend must never hold the asyncio event loop:
measured before the fix, `task.delay()` from an async handler blocked the
whole process for 64.3 s (redis result backend: 20 retries x 1 s). See
BoundedPublishTask in api/tasks/celery_app.py.
"""

import asyncio
import time

import pytest
from celery import Celery

from api.tasks import celery_app as celery_module
from api.tasks.celery_app import BoundedPublishTask, BrokerUnavailableError

MAX_BLOCK_SECONDS = 2.0


@pytest.fixture(autouse=True)
def _reset_breaker(monkeypatch):
    monkeypatch.setattr(celery_module, "_broker_down_until", 0.0)
    # Celery lets these env vars override Celery(broker=..., backend=...);
    # the in-memory apps below must not be silently redirected to redis.
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)


def _dead_app() -> Celery:
    app = Celery("dead", broker="redis://127.0.0.1:1/0", backend="redis://127.0.0.1:1/1", task_cls=BoundedPublishTask)

    @app.task(name="dead.noop")
    def noop():  # pragma: no cover -- never executed
        return 1

    return app


@pytest.mark.asyncio
async def test_dead_broker_dispatch_is_bounded_and_loop_stays_responsive():
    task = _dead_app().tasks["dead.noop"]
    ticks: list[float] = []

    async def ticker():
        while True:
            ticks.append(time.perf_counter())
            await asyncio.sleep(0.05)

    ticker_task = asyncio.create_task(ticker())
    await asyncio.sleep(0.2)
    started = time.perf_counter()
    with pytest.raises(BrokerUnavailableError):
        task.delay()
    first = time.perf_counter() - started
    started = time.perf_counter()
    with pytest.raises(BrokerUnavailableError):  # cooldown: instant, no second wait
        task.delay()
    second = time.perf_counter() - started
    await asyncio.sleep(0.2)
    ticker_task.cancel()

    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    assert first < MAX_BLOCK_SECONDS
    assert second < 0.1
    assert max(gaps) < MAX_BLOCK_SECONDS


@pytest.mark.asyncio
async def test_healthy_broker_dispatch_unchanged_inside_event_loop():
    app = Celery("ok", broker="memory://", backend="cache+memory://", task_cls=BoundedPublishTask)

    @app.task(name="ok.noop")
    def noop():  # pragma: no cover
        return 1

    result = noop.delay()
    assert result.id  # real AsyncResult returned from the publisher thread
    assert celery_module._broker_down_until == 0.0


def test_dispatch_outside_event_loop_is_untouched(monkeypatch):
    calls = []
    monkeypatch.setattr(celery_module, "_run_in_daemon_thread", lambda *a, **k: calls.append(a))
    app = Celery("sync", broker="memory://", backend="cache+memory://", task_cls=BoundedPublishTask)

    @app.task(name="sync.noop")
    def noop():  # pragma: no cover
        return 1

    assert noop.delay().id
    assert calls == []  # no thread hand-off for worker / sync callers


def test_real_celery_app_uses_bounded_base():
    assert issubclass(celery_module.celery_app.Task, BoundedPublishTask)
