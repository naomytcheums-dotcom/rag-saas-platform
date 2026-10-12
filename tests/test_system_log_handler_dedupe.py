"""SystemLogHandler must write every distinct WARNING+ record and write a record that reaches it twice only once.

Regression (found by tests/test_postgres_system_log_handler.py failing in a full batch): the handler de-duplicated by `id(record)` inside a
2-second window. Once a record is garbage collected its memory address is recycled by the next one, so DISTINCT records emitted back to
back were taken for duplicates and silently never reached `system_logs` (about 97 % lost in a tight loop). The fix marks the record object
itself, which is exact: a marker lives and dies with the record it describes.

In-memory database only: runs anywhere, needs no PostgreSQL."""

import gc
import logging
import uuid

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from api.models.admin import SystemLog
from api.security import system_log_handler
from api.security.system_log_handler import SystemLogHandler


@pytest.fixture
def engine(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    SystemLog.__table__.create(engine)
    monkeypatch.setattr(system_log_handler, "_sync_engine", engine)
    yield engine
    engine.dispose()


def _record(message: str) -> logging.LogRecord:
    return logging.LogRecord("test.dedupe", logging.WARNING, __file__, 1, message, None, None)


def _stored(engine, tag: str) -> list[str]:
    with Session(engine) as db:
        return list(db.scalars(select(SystemLog.message).where(SystemLog.message.like(f"%{tag}%")).order_by(SystemLog.message)))


def test_distinct_records_emitted_back_to_back_are_all_written(engine):
    tag = uuid.uuid4().hex
    handler = SystemLogHandler()
    for index in range(60):
        record = _record(f"distinct {index:03d} {tag}")
        handler.handle(record)
        del record
        gc.collect(0)  # frees the record, so the next one may be allocated at the same address
    assert len(_stored(engine, tag)) == 60


def test_one_record_reaching_two_handlers_is_written_once(engine):
    tag = uuid.uuid4().hex
    first, second = SystemLogHandler(), SystemLogHandler()
    record = _record(f"shared {tag}")
    first.handle(record)
    second.handle(record)
    assert _stored(engine, tag) == [f"shared {tag}"]


def test_the_same_message_emitted_twice_as_two_records_is_written_twice(engine):
    tag = uuid.uuid4().hex
    handler = SystemLogHandler()
    handler.handle(_record(f"again {tag}"))
    handler.handle(_record(f"again {tag}"))
    assert _stored(engine, tag) == [f"again {tag}", f"again {tag}"]


def test_a_failing_write_never_raises_and_does_not_mark_later_records_as_written(monkeypatch, engine):
    tag = uuid.uuid4().hex
    handler = SystemLogHandler()
    broken = create_engine("sqlite:////nonexistent-dir/none.db")
    monkeypatch.setattr(system_log_handler, "_sync_engine", broken)
    handler.handle(_record(f"lost {tag}"))  # must not raise
    monkeypatch.setattr(system_log_handler, "_sync_engine", engine)
    handler.handle(_record(f"kept {tag}"))
    assert _stored(engine, tag) == [f"kept {tag}"]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(SystemLog)) == 1
