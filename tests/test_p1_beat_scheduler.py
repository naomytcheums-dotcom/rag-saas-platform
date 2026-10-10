"""PROD-001: the beat scheduler must survive restarts, because production only has short worker bursts on fresh machines.

Redis is faked with a dict: the point is what the scheduler loads and saves, not Redis itself."""

import datetime as dt
from unittest.mock import patch

from api.tasks import beat_scheduler
from api.tasks.beat_scheduler import LAST_RUN_HASH, RedisPersistentScheduler
from api.tasks.celery_app import celery_app


class _FakeRedis:
    def __init__(self, stored=None):
        self.hash = dict(stored or {})
        self.writes = []

    def hgetall(self, key):
        assert key == LAST_RUN_HASH
        return dict(self.hash)

    def hset(self, key, field, value):
        assert key == LAST_RUN_HASH
        self.hash[field] = value
        self.writes.append(field)


def _scheduler(fake):
    with patch.object(beat_scheduler, "_redis", return_value=fake):
        scheduler = RedisPersistentScheduler(celery_app, lazy=True)
        scheduler.setup_schedule()
    return scheduler


def test_last_run_times_are_restored_from_redis_at_startup():
    recent = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=15)).isoformat()
    scheduler = _scheduler(_FakeRedis({"check-scheduled-reindexes": recent}))
    entry = scheduler.schedule["check-scheduled-reindexes"]
    assert entry.last_run_at.isoformat() == recent
    is_due, _next = entry.is_due()
    assert is_due is False  # it ran 15 seconds ago and runs every minute: not sent again immediately at start-up
    fresh = scheduler.schedule["check-scheduled-workflow-triggers"]
    assert fresh.last_run_at is not None


def test_a_task_that_became_due_while_nothing_was_running_is_due_at_the_next_start():
    long_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)).isoformat()
    scheduler = _scheduler(_FakeRedis({"check-scheduled-reindexes": long_ago}))
    is_due, _next = scheduler.schedule["check-scheduled-reindexes"].is_due()
    assert is_due is True


def test_dispatching_an_entry_persists_its_new_last_run_time():
    fake = _FakeRedis()
    scheduler = _scheduler(fake)
    entry = scheduler.schedule["check-scheduled-reindexes"]
    with patch.object(beat_scheduler, "_redis", return_value=fake):
        new_entry = scheduler.reserve(entry)
    assert fake.writes == ["check-scheduled-reindexes"]
    assert fake.hash["check-scheduled-reindexes"] == new_entry.last_run_at.isoformat()


def test_corrupt_stored_values_are_ignored():
    scheduler = _scheduler(_FakeRedis({"check-scheduled-reindexes": "not-a-date"}))
    assert "check-scheduled-reindexes" in scheduler.schedule


def test_the_schedule_keeps_working_when_redis_is_down():
    class _Down:
        def hgetall(self, key):
            raise ConnectionError("redis is down")

        def hset(self, key, field, value):
            raise ConnectionError("redis is down")

    scheduler = _scheduler(_Down())
    assert "check-scheduled-reindexes" in scheduler.schedule
    with patch.object(beat_scheduler, "_redis", return_value=_Down()):
        scheduler.reserve(scheduler.schedule["check-scheduled-reindexes"])  # must not raise


def test_every_beat_entry_is_loaded_by_the_scheduler():
    scheduler = _scheduler(_FakeRedis())
    assert set(celery_app.conf.beat_schedule) <= set(scheduler.schedule)
