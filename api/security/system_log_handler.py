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

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.admin import SystemLog
from api.security.logging_correlation import get_request_id, mask_sensitive

_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), pool_pre_ping=True, pool_size=2)
    return _sync_engine


class SystemLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
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
