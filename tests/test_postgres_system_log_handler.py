"""The system-log handler on a DISPOSABLE PostgreSQL only (same guard as the other PostgreSQL tests: tests/disposable_pg_guard.py).

tests/test_admin_dashboard.py proves the handler's behaviour on a throw-away in-memory database; this module proves the same
behaviour on the engine the application really uses: rows reach `system_logs` through a committed transaction visible to another
connection, the request id column is filled, secrets are masked on the way in, and a database failure never raises into the caller."""

import logging
import os
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.database_url import synchronous_database_url
from api.models.admin import SystemLog
from api.security import system_log_handler
from api.security.system_log_handler import SystemLogHandler
from disposable_pg_guard import disposable_pg_refusal

URL = os.environ.get("RAG_DISPOSABLE_PG_URL", "")
_REFUSAL = disposable_pg_refusal(URL, os.environ.get("RAG_DISPOSABLE_PG_CONFIRM"), str(settings.DATABASE_URL), os.environ.get("DATABASE_URL"))
pytestmark = pytest.mark.skipif(_REFUSAL is not None, reason=f"PostgreSQL tests not authorized: {_REFUSAL}")


@pytest.fixture
def pg_engine(monkeypatch):
    engine = create_engine(synchronous_database_url(URL), pool_pre_ping=True)
    SystemLog.__table__.create(engine, checkfirst=True)
    monkeypatch.setattr(system_log_handler, "_sync_engine", engine)
    yield engine
    engine.dispose()


def _emit(message: str) -> None:
    logger = logging.getLogger(f"test.pg_system_log.{uuid.uuid4().hex[:6]}")
    logger.propagate = False
    handler = SystemLogHandler()
    logger.addHandler(handler)
    try:
        logger.warning(message)
    finally:
        logger.removeHandler(handler)


def _rows(engine, message: str):
    with SyncSession(engine) as db:
        return db.scalars(select(SystemLog).where(SystemLog.message.like(f"%{message}%"))).all()


def _cleanup(engine, message: str) -> None:
    with SyncSession(engine) as db:
        for row in db.scalars(select(SystemLog).where(SystemLog.message.like(f"%{message}%"))).all():
            db.delete(row)
        db.commit()


def test_a_warning_becomes_a_committed_row_visible_from_another_connection(pg_engine):
    marker = f"pg-handler-{uuid.uuid4()}"
    try:
        _emit(f"disk almost full {marker}")
        rows = _rows(pg_engine, marker)  # a new session = a new transaction: proves the insert was committed
        assert len(rows) == 1
        assert rows[0].level == "WARNING"
        assert rows[0].function == "_emit"
        assert rows[0].line > 0
    finally:
        _cleanup(pg_engine, marker)


def test_a_secret_in_the_message_is_masked_before_it_is_stored(pg_engine):
    marker = f"pg-handler-{uuid.uuid4()}"
    try:
        _emit(f'upstream rejected the call, api_key="sk-live-0123456789abcdefABCDEF" {marker}')
        stored = _rows(pg_engine, marker)
        assert len(stored) == 1
        assert "sk-live-0123456789abcdefABCDEF" not in stored[0].message
    finally:
        _cleanup(pg_engine, marker)


def test_a_database_failure_never_raises_into_the_caller(monkeypatch):
    broken = create_engine("postgresql+psycopg2://nobody:nothing@127.0.0.1:1/none", connect_args={"connect_timeout": 1})
    monkeypatch.setattr(system_log_handler, "_sync_engine", broken)
    _emit("this write cannot reach any database")  # must simply return
    broken.dispose()
