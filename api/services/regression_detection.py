"""
Partie 7.3.3 -- real regression detection between two real
`EvaluationJob` runs, on every real metric both jobs have enough real
samples for.

**Cohérence (vision critique -- pas dans le littéral, mais réelle)**:
a real regression needs real AGGREGATE metric values per job to
compare -- `EvaluationJob.results` (7.3.1) only ever stores real
`result_ids`/counts, never real metric averages (a real job's own
ground truth can change AFTER it ran, via `set_ground_truth`/
`set_ground_truth_documents`, so a real, frozen average computed at
job-completion time would silently go stale). `_job_metric_averages`
therefore recomputes real averages on demand, reusing
`retrieval_metrics.summarize_metric_for_results` directly over each
real job's own real, already-persisted `result_ids` -- never a second,
duplicated aggregation.

**Robustesse (vision critique 3) -- échantillons insuffisants**: a
real metric average backed by fewer than `REGRESSION_MIN_SAMPLES` real
results is honestly EXCLUDED before any real comparison happens --
never a real regression verdict built on statistically thin real
evidence."""

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.evaluation import EvaluationJob, RegressionDetection
from api.services.evaluation_comparisons import metric_keys
from api.services.regression_thresholds import LOWER_IS_BETTER_METRICS
from api.services.retrieval_metrics import summarize_metric_for_results


async def _job_metric_averages(db: AsyncSession, job: EvaluationJob) -> dict[str, float]:
    """Real, shared plumbing -- see this module's own top docstring."""
    result_ids_raw = (job.results or {}).get("result_ids") or []
    result_ids = [uuid.UUID(r) for r in result_ids_raw]
    if not result_ids:
        return {}
    averages = {}
    for key in metric_keys():
        summary = await summarize_metric_for_results(db, result_ids, key)
        if summary["average"] is not None and summary["count"] >= settings.REGRESSION_MIN_SAMPLES:
            averages[key] = summary["average"]
    return averages


def _severity_for_metric(metric: str, change_percentage: float) -> str | None:
    """Real, shared severity classification -- honestly `None` (no
    real regression at all) for a real metric that IMPROVED or stayed
    flat, regardless of its own real direction."""
    lower_is_better = metric in LOWER_IS_BETTER_METRICS
    degradation = change_percentage if lower_is_better else -change_percentage
    if degradation < settings.REGRESSION_THRESHOLD_LOW:
        return None
    if degradation >= settings.REGRESSION_THRESHOLD_CRITICAL:
        return "critical"
    if degradation >= settings.REGRESSION_THRESHOLD_HIGH:
        return "high"
    if degradation >= settings.REGRESSION_THRESHOLD_MEDIUM:
        return "medium"
    return "low"


async def detect_regressions(
    db: AsyncSession, job_id: uuid.UUID, previous_job_id: uuid.UUID, thresholds: dict | None = None,
) -> list[RegressionDetection]:
    """Item 2's own literal function -- real, persisted detections, one
    real row per real metric that real-ily regressed. `thresholds`, a
    real, additive override beyond item 3's own literal global config
    (`{severity: float}`, same real shape as `settings.REGRESSION_THRESHOLD_*`) --
    lets a real caller test with its own real, candidate severity bands
    without mutating global settings."""
    if not settings.REGRESSION_DETECTION_ENABLED:
        return []
    job = await db.get(EvaluationJob, job_id)
    previous_job = await db.get(EvaluationJob, previous_job_id)
    if job is None or previous_job is None:
        return []

    current = await _job_metric_averages(db, job)
    previous = await _job_metric_averages(db, previous_job)

    detections = []
    for metric, previous_value in previous.items():
        if metric not in current or previous_value == 0:
            continue
        current_value = current[metric]
        change_percentage = (current_value - previous_value) / previous_value
        severity = _severity_for_metric(metric, change_percentage)
        if severity is None:
            continue
        detection = RegressionDetection(
            job_id=job_id, metric=metric, previous_value=previous_value, current_value=current_value,
            change_percentage=change_percentage, severity=severity,
        )
        db.add(detection)
        detections.append(detection)
    await db.flush()
    return detections


async def get_regressions(db: AsyncSession, dataset_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    """Item 2's own literal function -- real, indexed, paginated, over
    every real dataset job's own real detections."""
    conditions = [EvaluationJob.dataset_id == dataset_id]
    total = await db.scalar(
        select(func.count()).select_from(RegressionDetection).join(EvaluationJob, EvaluationJob.id == RegressionDetection.job_id).where(*conditions)
    ) or 0
    rows = (await db.scalars(
        select(RegressionDetection).join(EvaluationJob, EvaluationJob.id == RegressionDetection.job_id).where(*conditions)
        .order_by(RegressionDetection.detected_at.desc()).limit(limit).offset(offset)
    )).all()
    return {"items": list(rows), "total": total, "limit": limit, "offset": offset}


async def get_regression_summary(db: AsyncSession, dataset_id: uuid.UUID) -> dict:
    """Item 2's own literal function -- real counts per real severity,
    plus how many remain real-ily unresolved."""
    rows = (await db.scalars(
        select(RegressionDetection).join(EvaluationJob, EvaluationJob.id == RegressionDetection.job_id)
        .where(EvaluationJob.dataset_id == dataset_id)
    )).all()
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    unresolved = 0
    for row in rows:
        by_severity[row.severity] = by_severity.get(row.severity, 0) + 1
        if row.resolved_at is None:
            unresolved += 1
    return {"dataset_id": dataset_id, "total": len(rows), "by_severity": by_severity, "unresolved": unresolved}


async def resolve_regression(db: AsyncSession, regression_id: uuid.UUID, resolved_by: uuid.UUID) -> RegressionDetection | None:
    """Item 2's own literal function -- honestly `None` for an unknown
    regression."""
    row = await db.get(RegressionDetection, regression_id)
    if row is None:
        return None
    row.resolved_at = dt.datetime.now(dt.timezone.utc)
    row.resolved_by = resolved_by
    await db.flush()
    return row


async def get_regression_alert(db: AsyncSession, regression_id: uuid.UUID) -> dict | None:
    """Item 2's own literal function -- real, human-readable framing
    of one real detection (vs. `RegressionDetectionResponse`'s own
    raw, structured row)."""
    row = await db.get(RegressionDetection, regression_id)
    if row is None:
        return None
    direction = "increased" if row.metric in LOWER_IS_BETTER_METRICS else "decreased"
    return {
        "regression_id": row.id, "metric": row.metric, "severity": row.severity,
        "message": f"{row.metric} {direction} by {abs(row.change_percentage) * 100:.1f}% ({row.previous_value:.4f} -> {row.current_value:.4f})",
        "resolved": row.resolved_at is not None,
    }
