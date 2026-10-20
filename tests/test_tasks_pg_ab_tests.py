"""Celery tasks of api/tasks/ab_tests.py against a real PostgreSQL: significance snapshots, automatic decision, expiry of forgotten tests, report e-mail."""

import datetime as dt
import math
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import settings
from api.models.evaluation import ABTest, ABTestResult, ABTestStatus
from api.tasks.ab_tests import (
    _variance_and_mean, _welch_p_value, auto_decide_ab_tests, check_ab_test_significance, complete_expired_ab_tests, send_ab_test_report,
)
from pg_tasks_support import organization, require_postgres, user

NOW = dt.datetime.now(dt.timezone.utc)


def _stats(values: list[float]) -> dict:
    return {"count": len(values), "sum": sum(values), "sum_sq": sum(v * v for v in values)}


CLEAR_A = _stats([1.0, 1.1, 0.9, 1.0, 1.05, 0.95] * 5)
CLEAR_B = _stats([2.0, 2.1, 1.9, 2.0, 2.05, 1.95] * 5)


@pytest.fixture
def engine():
    return require_postgres()


def _test(org_id, **fields) -> ABTest:
    base = dict(organization_id=org_id, name="t", variant_a={"p": "a"}, variant_b={"p": "b"}, status=ABTestStatus.running, target_metric="satisfaction",
                min_sample_size=10, confidence_level=0.95, metrics={"a": {"satisfaction": CLEAR_A}, "b": {"satisfaction": CLEAR_B}})
    return ABTest(**{**base, **fields})


def _save(engine, *tests) -> list[uuid.UUID]:
    with Session(engine) as db:
        db.add_all(tests)
        db.commit()
        return [t.id for t in tests]


def _reload(engine, test_id) -> ABTest:
    with Session(engine) as db:
        return db.get(ABTest, test_id)


def test_welch_p_value_edge_cases_and_the_clear_difference():
    assert _welch_p_value({"count": 1, "sum": 1, "sum_sq": 1}, CLEAR_B) is None
    flat = _stats([1.0] * 5)
    assert _welch_p_value(flat, _stats([1.0] * 5)) == 1.0  # no variance, same mean
    assert _welch_p_value(flat, _stats([2.0] * 5)) == 0.0  # no variance, different means
    assert _welch_p_value(CLEAR_A, CLEAR_B) < 0.001
    mean, variance = _variance_and_mean(_stats([1.0, 3.0]))
    assert mean == 2.0 and math.isclose(variance, 1.0)


def test_the_significance_sweep_snapshots_both_variants_of_running_tests_only(engine):
    with organization(engine, "abtest") as org_id:
        running, paused, no_data = _test(org_id, name="running"), _test(org_id, name="paused", status=ABTestStatus.paused), _test(org_id, name="nodata", metrics={"a": {}, "b": {}})
        ids = _save(engine, running, paused, no_data)

        assert check_ab_test_significance() >= 2

        with Session(engine) as db:
            rows = db.scalars(select(ABTestResult).where(ABTestResult.ab_test_id == ids[0])).all()
            assert sorted(r.variant for r in rows) == ["a", "b"]
            assert all(r.sample_count == 30 and r.is_significant is True and r.p_value < 0.05 for r in rows)
            assert db.scalars(select(ABTestResult).where(ABTestResult.ab_test_id.in_(ids[1:]))).all() == []


def test_the_automatic_decision_is_off_by_default_and_picks_the_higher_mean_when_on(engine, monkeypatch):
    with organization(engine, "abdecide") as org_id:
        better_is_higher = _test(org_id, name="higher")
        too_small = _test(org_id, name="small", min_sample_size=1000)
        close = _test(org_id, name="close", metrics={"a": {"satisfaction": CLEAR_A}, "b": {"satisfaction": CLEAR_A}})
        ids = _save(engine, better_is_higher, too_small, close)

        monkeypatch.setattr(settings, "AB_TEST_AUTO_DECIDE", False)
        assert auto_decide_ab_tests() == 0
        assert _reload(engine, ids[0]).status == ABTestStatus.running

        monkeypatch.setattr(settings, "AB_TEST_AUTO_DECIDE", True)
        assert auto_decide_ab_tests() >= 1
        decided = _reload(engine, ids[0])
        assert decided.status == ABTestStatus.completed and decided.winner == "b" and decided.end_date is not None
        assert _reload(engine, ids[1]).status == ABTestStatus.running  # not enough samples
        assert _reload(engine, ids[2]).status == ABTestStatus.running  # no significant difference


def test_for_a_lower_is_better_metric_the_lower_mean_wins(engine, monkeypatch):
    monkeypatch.setattr(settings, "AB_TEST_AUTO_DECIDE", True)
    with organization(engine, "ablower") as org_id:
        latency = _test(org_id, name="latency", target_metric="avg_response_time", metrics={"a": {"avg_response_time": CLEAR_A}, "b": {"avg_response_time": CLEAR_B}})
        (test_id,) = _save(engine, latency)

        auto_decide_ab_tests()

        assert _reload(engine, test_id).winner == "a"


def test_tests_running_longer_than_the_maximum_are_completed_with_no_winner(engine):
    with organization(engine, "abexpire") as org_id:
        forgotten = _test(org_id, name="forgotten", start_date=NOW - dt.timedelta(days=settings.AB_TEST_MAX_DURATION_DAYS + 5))
        forgotten_paused = _test(org_id, name="paused-forgotten", status=ABTestStatus.paused, start_date=NOW - dt.timedelta(days=settings.AB_TEST_MAX_DURATION_DAYS + 5))
        recent = _test(org_id, name="recent", start_date=NOW - dt.timedelta(days=1))
        ids = _save(engine, forgotten, forgotten_paused, recent)

        assert complete_expired_ab_tests() >= 2

        for test_id in ids[:2]:
            done = _reload(engine, test_id)
            assert done.status == ABTestStatus.completed and done.winner == "none" and done.end_date is not None
        assert _reload(engine, ids[2]).status == ABTestStatus.running


def test_the_report_goes_to_the_creator_and_degrades_to_false_without_one_or_on_failure(engine, monkeypatch):
    sent = []
    monkeypatch.setattr("api.services.email.send_ab_test_report_email", lambda *args: sent.append(args))
    with organization(engine, "abreport") as org_id, user(engine, "creator") as (creator_id, creator_email):
        reported, orphan = _test(org_id, name="reported", created_by=creator_id), _test(org_id, name="orphan")
        reported_id, orphan_id = _save(engine, reported, orphan)

        assert send_ab_test_report(str(reported_id)) is True
        assert sent and sent[0][0] == creator_email and sent[0][1] == "reported"
        assert send_ab_test_report(str(orphan_id)) is False  # no creator
        assert send_ab_test_report(str(uuid.uuid4())) is False  # unknown test

        def boom(*args):
            raise RuntimeError("mail provider down")

        monkeypatch.setattr("api.services.email.send_ab_test_report_email", boom)
        assert send_ab_test_report(str(reported_id)) is False  # a delivery failure never raises out of the task
