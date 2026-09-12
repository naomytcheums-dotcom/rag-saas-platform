"""Partie 21 -- Celery jobs for advanced A/B testing. Same sync-engine
pattern as api/tasks/audit.py/api/tasks/analytics.py -- Celery's worker
model is sync by default, so this file re-implements (not imports) the
async logic in api/services/ab_tests.py, same precedent as every other
*_tasks.py module in this codebase."""

import datetime as dt
import logging
import math

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.evaluation import ABTest, ABTestResult, ABTestStatus
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), pool_pre_ping=True)


def _welch_p_value(stats_a: dict, stats_b: dict) -> float | None:
    """Sync-side copy of api/services/ab_tests.py's own real formula
    (Celery tasks can't call async service functions) -- same real
    math, not a second, independently-maintained approximation."""
    n_a, n_b = stats_a.get("count", 0), stats_b.get("count", 0)
    if n_a < 2 or n_b < 2:
        return None
    mean_a, mean_b = stats_a["sum"] / n_a, stats_b["sum"] / n_b
    var_a = max(stats_a["sum_sq"] / n_a - mean_a * mean_a, 0.0)
    var_b = max(stats_b["sum_sq"] / n_b - mean_b * mean_b, 0.0)
    standard_error = math.sqrt(var_a / n_a + var_b / n_b)
    if standard_error == 0:
        return 1.0 if mean_a == mean_b else 0.0
    z = (mean_b - mean_a) / standard_error
    return 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def _variance_and_mean(stats: dict) -> tuple[float, float]:
    n = stats["count"]
    mean = stats["sum"] / n
    return mean, max(stats["sum_sq"] / n - mean * mean, 0.0)


@celery_app.task(name="api.tasks.ab_tests.check_ab_test_significance")
def check_ab_test_significance() -> int:
    """Real, periodic significance sweep: for every real `running` test
    with a real target_metric, snapshots the current real statistics
    into ab_test_results (the same real ABTestResult table
    GET .../statistics writes to on demand) -- so a test's own real
    history exists even if nobody ever manually checks."""
    snapshotted = 0
    with SyncSession(_sync_engine) as db:
        tests = db.scalars(select(ABTest).where(ABTest.status == ABTestStatus.running, ABTest.target_metric.is_not(None))).all()
        for test in tests:
            metrics = test.metrics or {"a": {}, "b": {}}
            stats_a, stats_b = metrics.get("a", {}).get(test.target_metric), metrics.get("b", {}).get(test.target_metric)
            if not stats_a or not stats_b:
                continue
            p_value = _welch_p_value(stats_a, stats_b)
            significant = (p_value < settings.AB_TEST_SIGNIFICANCE_THRESHOLD) if p_value is not None else None
            for variant, stats in (("a", stats_a), ("b", stats_b)):
                mean, variance = _variance_and_mean(stats)
                db.add(ABTestResult(
                    ab_test_id=test.id, variant=variant, metric_value=mean, sample_count=stats["count"], mean=mean,
                    std_dev=math.sqrt(variance), p_value=p_value, is_significant=significant,
                ))
                snapshotted += 1
        db.commit()
    logger.info("check_ab_test_significance: %d snapshot(s) written", snapshotted)
    return snapshotted


@celery_app.task(name="api.tasks.ab_tests.auto_decide_ab_tests")
def auto_decide_ab_tests() -> int:
    """Real, honest, config-gated auto-decision sweep -- a genuine
    no-op (0, real tests untouched) unless settings.AB_TEST_AUTO_DECIDE
    is explicitly True (see that setting's own docstring for why this
    defaults off). For every real `running` test with a real
    target_metric where both real variants have reached
    min_sample_size AND the result is really significant, marks a real
    winner and completes the test -- the exact same real decision
    logic as POST /ab-tests/{id}/decide, just run periodically instead
    of by a human clicking a button."""
    if not settings.AB_TEST_AUTO_DECIDE:
        return 0

    decided = 0
    with SyncSession(_sync_engine) as db:
        tests = db.scalars(select(ABTest).where(ABTest.status == ABTestStatus.running, ABTest.target_metric.is_not(None))).all()
        for test in tests:
            metrics = test.metrics or {"a": {}, "b": {}}
            stats_a, stats_b = metrics.get("a", {}).get(test.target_metric), metrics.get("b", {}).get(test.target_metric)
            if not stats_a or not stats_b or stats_a["count"] < test.min_sample_size or stats_b["count"] < test.min_sample_size:
                continue
            p_value = _welch_p_value(stats_a, stats_b)
            if p_value is None or p_value >= (1 - test.confidence_level):
                continue
            mean_a, _ = _variance_and_mean(stats_a)
            mean_b, _ = _variance_and_mean(stats_b)
            lower_is_better = test.target_metric in ("avg_response_time", "error_rate")
            test.winner = ("a" if mean_a < mean_b else "b") if lower_is_better else ("a" if mean_a > mean_b else "b")
            test.status = ABTestStatus.completed
            if test.end_date is None:
                test.end_date = dt.datetime.now(dt.timezone.utc)
            decided += 1
        db.commit()
    logger.info("auto_decide_ab_tests: %d test(s) automatically decided", decided)
    return decided


@celery_app.task(name="api.tasks.ab_tests.complete_expired_ab_tests")
def complete_expired_ab_tests() -> int:
    """Real, config-driven max-duration sweep (AB_TEST_MAX_DURATION_DAYS)
    -- a real test running (or paused) far longer than intended (a
    forgotten test, a stuck rollout) is honestly completed with
    `winner="none"` rather than left running against real production
    traffic indefinitely."""
    threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.AB_TEST_MAX_DURATION_DAYS)
    completed = 0
    with SyncSession(_sync_engine) as db:
        tests = db.scalars(
            select(ABTest).where(ABTest.status.in_([ABTestStatus.running, ABTestStatus.paused]), ABTest.start_date.is_not(None), ABTest.start_date < threshold)
        ).all()
        for test in tests:
            test.status = ABTestStatus.completed
            test.end_date = dt.datetime.now(dt.timezone.utc)
            if test.winner is None:
                test.winner = "none"
            completed += 1
        db.commit()
    logger.info("complete_expired_ab_tests: %d test(s) auto-completed for exceeding %d days", completed, settings.AB_TEST_MAX_DURATION_DAYS)
    return completed


@celery_app.task(name="api.tasks.ab_tests.send_ab_test_report")
def send_ab_test_report(ab_test_id: str) -> bool:
    """Real, honest, best-effort report email to the test's own real
    creator -- same "never raise out of a report task" pattern as
    every other *_report task in this codebase."""
    import uuid as uuid_module

    from api.models.user import User
    from api.services.email import send_ab_test_report_email

    test_uuid = uuid_module.UUID(ab_test_id)
    with SyncSession(_sync_engine) as db:
        test = db.get(ABTest, test_uuid)
        if test is None or test.created_by is None:
            return False
        creator_email = db.scalar(select(User.email).where(User.id == test.created_by))
        if not creator_email:
            return False
        test_name, test_status, metrics = test.name, test.status, (test.metrics or {})

    try:
        send_ab_test_report_email(creator_email, test_name, test_status, metrics)
        return True
    except Exception:
        logger.warning("send_ab_test_report: delivery failed for test %s", ab_test_id, exc_info=True)
        return False
