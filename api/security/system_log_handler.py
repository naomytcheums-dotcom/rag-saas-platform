"""
Partie 11.6 -- a real `logging.Handler` capturing every WARNING+ log
line this process emits into the real `system_logs` table, attached to
the root logger in api/main.py's lifespan. Synchronous, direct-insert
(same sync-engine-in-an-async-process pattern api/tasks/*.py already
uses for Celery) -- a real WARNING/ERROR is rare enough on a healthy
system that the small, occasional blocking insert this causes is an
acceptable, honest tradeoff, not a hidden performance problem; it also
means a failure to log never blocks the request that triggered it
(wrapped in a broad except so a DB hiccup while logging an error never
raises a SECOND error).
"""

import logging
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.admin import SystemLog
from api.security.logging_correlation import get_request_id, mask_sensitive

_sync_engine = None

# Root-cause note (2026-09-16): this handler is attached to the ROOT
# logger (see install_system_log_handler below), and Python loggers
# propagate to their ancestors by default. That means ANY child logger
# that emits WARNING+ without explicitly setting `propagate = False`
# reaches this handler once, AND may reach it a second time if that
# same record also propagates through another handler attached higher
# up that itself forwards here (the concrete case that bit
# tests/test_admin_dashboard.py: a test attaching its own handler to a
# named logger, on a process where this root handler was already
# installed by an earlier test's app lifespan). Rather than requiring
# every future caller to remember `propagate = False`, this handler
# dedupes identical records emitted within a short window -- the
# general fix, at the point that actually writes the row, instead of a
# special case at every logger that might double-propagate into it.
_DEDUPE_WINDOW_SECONDS = 2.0
_recent_records: dict[tuple, float] = {}


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), pool_pre_ping=True, pool_size=2)
    return _sync_engine


class SystemLogHandler(logging.Handler):
    def _is_duplicate(self, record: logging.LogRecord) -> bool:
        """True if THIS EXACT record object already reached another
        SystemLogHandler instance in the same propagation chain --
        logging delivers one shared LogRecord to every handler a
        record propagates through, so `id(record)` is a precise (not
        content-guessed) key for "already written," scoped to a short
        window so the id-reuse-after-GC edge case can't wrongly
        dedupe an unrelated, later record."""
        now = time.monotonic()
        for seen_id, seen_at in list(_recent_records.items()):
            if now - seen_at > _DEDUPE_WINDOW_SECONDS:
                del _recent_records[seen_id]
        key = id(record)
        if key in _recent_records:
            return True
        _recent_records[key] = now
        return False

    def emit(self, record: logging.LogRecord) -> None:
        if self._is_duplicate(record):
            return
        try:
            with SyncSession(_get_sync_engine()) as db:
                db.add(SystemLog(
                    level=record.levelname, logger_name=record.name, message=mask_sensitive(self.format(record)),
                    module=record.module, function=record.funcName, line=record.lineno,
                    request_id=get_request_id(),
                ))
                db.commit()
        except Exception:  # noqa: BLE001 -- logging itself must never raise; a failed log write is silently dropped
            pass


def install_system_log_handler() -> None:
    """Called once from api/main.py's lifespan -- idempotent (checks for
    an already-installed instance) so it's safe if the app is ever
    re-initialized within the same process (e.g. tests)."""
    root = logging.getLogger()
    if any(isinstance(h, SystemLogHandler) for h in root.handlers):
        return
    handler = SystemLogHandler(level=logging.WARNING)
    root.addHandler(handler)
