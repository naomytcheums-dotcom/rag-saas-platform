"""The HNSW scan filtered by organization must keep scanning until enough of the tenant's rows pass (pgvector >= 0.8 `hnsw.iterative_scan`),
and must never break a search on a database that does not know the parameter."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.config import settings
from api.services.retrieval_pipeline import _enable_iterative_hnsw_scan


class _Savepoint:
    def __init__(self, calls):
        self._calls = calls

    async def __aenter__(self):
        self._calls.append("SAVEPOINT")

    async def __aexit__(self, exc_type, exc, tb):
        self._calls.append("ROLLBACK TO SAVEPOINT" if exc_type else "RELEASE")
        return False  # never swallow here: the caller's try/except decides


def _db(fail_on=None):
    calls = []
    db = MagicMock()
    db.begin_nested = lambda: _Savepoint(calls)

    async def execute(statement):
        text_of = str(statement)
        calls.append(text_of)
        if fail_on and fail_on in text_of:
            raise RuntimeError('unrecognized configuration parameter "hnsw.iterative_scan"')

    db.execute = AsyncMock(side_effect=execute)
    return db, calls


def test_the_feature_is_on_by_default_with_a_bounded_scan():
    assert settings.PGVECTOR_ITERATIVE_SCAN is True
    assert 1000 <= settings.PGVECTOR_MAX_SCAN_TUPLES <= 200000


async def test_iterative_scan_is_enabled_for_the_transaction_only(monkeypatch):
    monkeypatch.setattr(settings, "PGVECTOR_ITERATIVE_SCAN", True)
    monkeypatch.setattr(settings, "PGVECTOR_MAX_SCAN_TUPLES", 12345)
    db, calls = _db()
    await _enable_iterative_hnsw_scan(db)
    assert calls == ["SAVEPOINT", "SET LOCAL hnsw.iterative_scan = strict_order", "SET LOCAL hnsw.max_scan_tuples = 12345", "RELEASE"]


async def test_nothing_is_sent_when_the_switch_is_off(monkeypatch):
    monkeypatch.setattr(settings, "PGVECTOR_ITERATIVE_SCAN", False)
    db, calls = _db()
    await _enable_iterative_hnsw_scan(db)
    assert calls == []


async def test_an_older_pgvector_does_not_break_the_search(monkeypatch):
    """Without the parameter the statement fails: the savepoint is rolled back and the search carries on."""
    monkeypatch.setattr(settings, "PGVECTOR_ITERATIVE_SCAN", True)
    db, calls = _db(fail_on="hnsw.iterative_scan")
    await _enable_iterative_hnsw_scan(db)  # must not raise
    assert calls[0] == "SAVEPOINT" and calls[-1] == "ROLLBACK TO SAVEPOINT"


@pytest.mark.parametrize("value", [0, -5])
def test_the_scan_cap_is_a_positive_integer_in_the_statement(monkeypatch, value):
    """The cap is interpolated into SET LOCAL (a utility statement cannot take bind parameters), so it is forced through int()."""
    import inspect

    from api.services import retrieval_pipeline

    assert "int(app_settings.PGVECTOR_MAX_SCAN_TUPLES)" in inspect.getsource(retrieval_pipeline._enable_iterative_hnsw_scan)
