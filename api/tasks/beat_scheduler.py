"""Celery beat scheduler that remembers when each periodic task last ran, in Redis (PROD-001).

Production has no always-on beat service: the only worker is the scheduled GitHub Actions burst (`.github/workflows/celery-worker.yml`),
a fresh machine every 10 minutes. With Celery's default in-memory scheduler every restart forgets the schedule, so interval and daily/
monthly entries (invoices, monthly credits, reminders, GDPR purges, SSL renewals) either fire on every start or, for a cron time that
falls outside the burst window, never. This scheduler loads each entry's `last_run_at` from Redis at start-up and saves it after every
dispatch, so an entry that became due while no process was running is sent by the next burst, and one that already ran is not sent twice.

Run it with `celery -A api.tasks.celery_app beat --scheduler api.tasks.beat_scheduler:RedisPersistentScheduler`. If Redis cannot be
reached it degrades to the stock in-memory behavior (and logs it) rather than stopping the schedule."""

import datetime as dt
import logging

from celery.beat import Scheduler

from api.config import settings

logger = logging.getLogger(__name__)

LAST_RUN_HASH = "celery:beat:last_run_at"


def _redis():
    import redis

    return redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=5, socket_connect_timeout=5, decode_responses=True)


class RedisPersistentScheduler(Scheduler):
    """Stock beat scheduler plus a Redis-backed `last_run_at` per entry."""

    def setup_schedule(self):
        super().setup_schedule()
        try:
            stored = _redis().hgetall(LAST_RUN_HASH)
        except Exception as exc:  # noqa: BLE001 -- the schedule must keep working without persistence
            logger.warning("beat: could not load last run times from Redis (%s); starting from a blank state", type(exc).__name__)
            return
        restored = 0
        for name, entry in self.schedule.items():
            raw = stored.get(name)
            if not raw:
                continue
            try:
                last_run = dt.datetime.fromisoformat(raw)
            except ValueError:
                continue
            entry.last_run_at = last_run if last_run.tzinfo else last_run.replace(tzinfo=dt.timezone.utc)
            restored += 1
        logger.info("beat: restored the last run time of %d of %d scheduled tasks", restored, len(self.schedule))

    def reserve(self, entry):
        new_entry = super().reserve(entry)
        try:
            _redis().hset(LAST_RUN_HASH, new_entry.name, new_entry.last_run_at.isoformat())
        except Exception as exc:  # noqa: BLE001
            logger.warning("beat: could not persist the last run time of %s (%s)", new_entry.name, type(exc).__name__)
        return new_entry
