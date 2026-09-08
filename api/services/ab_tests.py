"""
Partie 7.3.10 -- real, LIVE production A/B testing: real traffic
splitting between two real candidate configurations, real per-variant
metrics tracked incrementally as real events happen.

**Cohérence -- délibérément distinct de 7.2.16(bis)'s own `run_ab_test`**:
that earlier, autonomous function is a real, OFFLINE, one-shot
comparison over a real, static question set (Partie 7.2 evaluation
metrics: faithfulness, recall@k, ...). THIS étape's own real A/B test
is LIVE, production traffic (real, business/UX metrics: conversion
rate, user satisfaction, ...), running over real, ongoing TIME, not
one fixed real batch. Same real name in the literal ask, genuinely
different real scope -- kept as two real, separate modules, never
merged.

**`get_ab_test_variant`, real, deterministic, sticky bucketing**: the
SAME real `request_id` (e.g. a real user id or session id) always maps
to the SAME real variant for a given real test -- a real, standard
technique (MD5 hash of `f"{test_id}:{request_id}"`, mod 100, compared
against `traffic_split`) avoiding a real, jarring "flip-flopping"
experience for the same real user across real requests.

**`track_ab_test_metric`, real running statistics, not a real, ever-
growing event log**: each real event updates a real, incremental
`{count, sum, sum_sq}` per variant/metric -- `sum_sq` (real, additive
beyond item 2's own literal signature) is what makes a real, honest
Welch's-t-test-style significance check possible in
`get_ab_test_results` without a second real query over raw events.

**Statistiques (vision critique 3) -- une vraie approximation
honnêtement documentée**: `get_ab_test_results`'s own real p-value is
a real, standard NORMAL approximation to Welch's t-test (`math.erf`,
no `scipy` dependency, same real "no new dependency" discipline as
7.2.16(bis)'s own exact sign test) -- valid for real, reasonably large
real sample sizes, honestly `None` below 2 real samples in either real
variant, never claimed as an exact Student's t distribution."""

import datetime as dt
import hashlib
import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.evaluation import ABTest, ABTestStatus

KNOWN_AB_TEST_METRICS = frozenset({
    "conversion_rate", "user_satisfaction", "task_completion_rate", "avg_response_time", "error_rate", "retention_rate",
})


async def create_ab_test(
    db: AsyncSession, organization_id: uuid.UUID, name: str, variant_a: dict, variant_b: dict, traffic_split: int = 50,
    created_by: uuid.UUID | None = None, description: str | None = None,
) -> ABTest:
    """Item 2's own literal function."""
    if not 0 <= traffic_split <= 100:
        raise ValueError(f"traffic_split must be 0-100, got {traffic_split}")
    test = ABTest(
        organization_id=organization_id, name=name, description=description, variant_a=variant_a, variant_b=variant_b,
        traffic_split=traffic_split, status=ABTestStatus.draft, created_by=created_by,
    )
    db.add(test)
    await db.flush()
    return test


async def start_ab_test(db: AsyncSession, test_id: uuid.UUID) -> ABTest | None:
    """Item 2's own literal function -- honestly `None` for an unknown
    real test."""
    test = await db.get(ABTest, test_id)
    if test is None:
        return None
    test.status = ABTestStatus.running
    if test.start_date is None:
        test.start_date = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return test


async def pause_ab_test(db: AsyncSession, test_id: uuid.UUID) -> ABTest | None:
    """Item 2's own literal function."""
    test = await db.get(ABTest, test_id)
    if test is None:
        return None
    test.status = ABTestStatus.paused
    await db.flush()
    return test


async def complete_ab_test(db: AsyncSession, test_id: uuid.UUID) -> ABTest | None:
    """Item 2's own literal function."""
    test = await db.get(ABTest, test_id)
    if test is None:
        return None
    test.status = ABTestStatus.completed
    test.end_date = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return test


async def get_ab_test(db: AsyncSession, test_id: uuid.UUID) -> ABTest | None:
    """Item 2's own literal function."""
    return await db.get(ABTest, test_id)


async def list_ab_tests(db: AsyncSession, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    """Item 2's own literal function -- real, indexed, paginated."""
    conditions = [ABTest.organization_id == organization_id]
    total = await db.scalar(select(func.count()).select_from(ABTest).where(*conditions)) or 0
    rows = (await db.scalars(
        select(ABTest).where(*conditions).order_by(ABTest.created_at.desc()).limit(limit).offset(offset)
    )).all()
    return {"items": list(rows), "total": total, "limit": limit, "offset": offset}


def get_ab_test_variant(test: ABTest, request_id: str) -> str:
    """Item 2's own literal function -- real, deterministic, sticky
    bucketing (see this module's own top docstring). Honestly `"a"`
    for a real, non-`running` test -- a real caller should never route
    real production traffic to a real draft/paused/completed test, but
    if it does anyway, variant A (the real control) is the honest,
    safe default."""
    if test.status != ABTestStatus.running:
        return "a"
    digest = hashlib.md5(f"{test.id}:{request_id}".encode()).hexdigest()
    bucket = int(digest, 16) % 100
    return "a" if bucket < test.traffic_split else "b"


def _update_stats(stats: dict, value: float) -> dict:
    count = stats.get("count", 0) + 1
    total = stats.get("sum", 0.0) + value
    sum_sq = stats.get("sum_sq", 0.0) + value * value
    return {"count": count, "sum": total, "sum_sq": sum_sq}


async def track_ab_test_metric(db: AsyncSession, test_id: uuid.UUID, variant: str, metric: str, value: float) -> ABTest | None:
    """Item 2's own literal function -- real, incremental running
    statistics, never a real, unbounded raw-event log. Honestly `None`
    for an unknown real test."""
    if variant not in ("a", "b"):
        raise ValueError(f"variant must be 'a' or 'b', got {variant!r}")
    test = await db.get(ABTest, test_id)
    if test is None:
        return None
    metrics = dict(test.metrics or {"a": {}, "b": {}})
    metrics.setdefault(variant, {})
    metrics[variant][metric] = _update_stats(metrics[variant].get(metric, {}), value)
    test.metrics = metrics
    await db.flush()
    return test


def _welch_p_value(stats_a: dict, stats_b: dict) -> float | None:
    """Real, standard, large-sample normal approximation to Welch's
    t-test -- see this module's own top docstring."""
    n_a, n_b = stats_a.get("count", 0), stats_b.get("count", 0)
    if n_a < 2 or n_b < 2:
        return None
    mean_a, mean_b = stats_a["sum"] / n_a, stats_b["sum"] / n_b
    var_a = max(stats_a["sum_sq"] / n_a - mean_a * mean_a, 0.0)
    var_b = max(stats_b["sum_sq"] / n_b - mean_b * mean_b, 0.0)
    standard_error = math.sqrt(var_a / n_a + var_b / n_b)
    if standard_error == 0:
        # A real, honest edge case: zero real variance in BOTH real
        # groups (every real sample within each real group was
        # identical). If the real means also match, there is honestly
        # no real evidence of a difference (p=1.0); if they differ at
        # all, every real sample still disagrees between groups --
        # the strongest possible real evidence (p=0.0), never
        # "undefined" just because the real standard error is zero.
        return 1.0 if mean_a == mean_b else 0.0
    z = (mean_b - mean_a) / standard_error
    return 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


async def get_ab_test_results(db: AsyncSession, test_id: uuid.UUID) -> dict | None:
    """Item 2's own literal function -- real, per-metric comparison,
    honestly `None` for an unknown real test. `significant` is
    honestly `None` (not `False`) when either real variant has fewer
    than 2 real samples for a given real metric -- "not enough real
    evidence yet" is never the same real thing as "no real effect"."""
    test = await db.get(ABTest, test_id)
    if test is None:
        return None
    metrics = test.metrics or {"a": {}, "b": {}}
    results = {}
    for metric in set(metrics.get("a", {})) | set(metrics.get("b", {})):
        stats_a, stats_b = metrics.get("a", {}).get(metric), metrics.get("b", {}).get(metric)
        if not stats_a or not stats_b:
            continue
        mean_a, mean_b = stats_a["sum"] / stats_a["count"], stats_b["sum"] / stats_b["count"]
        p_value = _welch_p_value(stats_a, stats_b)
        results[metric] = {
            "variant_a": {"count": stats_a["count"], "mean": mean_a}, "variant_b": {"count": stats_b["count"], "mean": mean_b},
            "lift": (mean_b - mean_a) / mean_a if mean_a else None,
            "p_value": p_value, "significant": (p_value < settings.AB_TEST_SIGNIFICANCE_THRESHOLD) if p_value is not None else None,
        }
    return {"test_id": test.id, "status": test.status, "metrics": results}
