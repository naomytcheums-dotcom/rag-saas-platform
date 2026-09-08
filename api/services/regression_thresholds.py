"""
Partie 7.3.9 -- real, per-organization, per-metric quality floors/
ceilings, checked against a real, given metrics dict.

**Cohérence (vision critique 1) -- une vraie direction par métrique,
partagée avec 7.3.3**: a real threshold's own real MEANING depends on
whether higher is better (`faithfulness`, `recall@5`, ...) or lower is
better (`hallucination_rate`, `latency`, `cost_per_request`) --
`LOWER_IS_BETTER_METRICS` is the one real, shared, documented
whitelist both this module's own `check_regression_thresholds` AND
`regression_detection.py`'s own severity classification reuse, so the
two étapes' real notion of "worse" never silently diverges.

**`DEFAULT_REGRESSION_THRESHOLDS`, a real, documented reference, not
auto-seeded rows**: item 3's own literal 7 default values are exposed
here for real, informational reuse (e.g. a real UI's own placeholder
values) -- never automatically inserted as real per-organization rows
on organization creation, same real "resolves to defaults until an
Owner explicitly opts in" precedent as `organization_settings.py`'s
own `DEFAULT_SETTINGS`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.evaluation import RegressionThreshold

LOWER_IS_BETTER_METRICS = frozenset({"hallucination_rate", "latency", "cost_per_request"})

DEFAULT_REGRESSION_THRESHOLDS: dict[str, float] = {
    "faithfulness": 0.7, "groundedness": 0.7, "hallucination_rate": 0.2, "answer_relevance": 0.8,
    "recall_at_5": 0.6, "latency": 2000.0, "cost_per_request": 0.05,
}


async def set_regression_threshold(
    db: AsyncSession, organization_id: uuid.UUID, metric: str, threshold: float, severity: str, created_by: uuid.UUID | None = None,
) -> RegressionThreshold:
    """Item 2's own literal function -- real UPSERT: a real, existing
    threshold for this exact real `(organization_id, metric)` pair is
    updated in place (matching this table's own real unique
    constraint), never a real, silently duplicated second row."""
    existing = await db.scalar(
        select(RegressionThreshold).where(RegressionThreshold.organization_id == organization_id, RegressionThreshold.metric == metric)
    )
    if existing is not None:
        existing.threshold = threshold
        existing.severity = severity
        existing.enabled = True
        await db.flush()
        return existing

    row = RegressionThreshold(organization_id=organization_id, metric=metric, threshold=threshold, severity=severity, created_by=created_by)
    db.add(row)
    await db.flush()
    return row


async def get_regression_threshold(db: AsyncSession, threshold_id: uuid.UUID) -> RegressionThreshold | None:
    """Real, additive: `GET /thresholds/{id}`'s own literal endpoint
    needs a real, single-row getter this étape's own literal function
    list didn't separately name."""
    return await db.get(RegressionThreshold, threshold_id)


async def get_regression_thresholds(db: AsyncSession, organization_id: uuid.UUID) -> list[RegressionThreshold]:
    """Item 2's own literal function."""
    rows = (await db.scalars(select(RegressionThreshold).where(RegressionThreshold.organization_id == organization_id))).all()
    return list(rows)


async def check_regression_thresholds(db: AsyncSession, organization_id: uuid.UUID, metrics: dict[str, float]) -> list[dict]:
    """Item 2's own literal function -- real violations only; a real
    metric this organization has no real, enabled threshold for (or
    that is simply absent from the given real `metrics` dict) is
    honestly skipped, never a fabricated pass or fail."""
    thresholds = await get_regression_thresholds(db, organization_id)
    violations = []
    for t in thresholds:
        if not t.enabled or t.metric not in metrics:
            continue
        value = metrics[t.metric]
        lower_is_better = t.metric in LOWER_IS_BETTER_METRICS
        violated = value > t.threshold if lower_is_better else value < t.threshold
        if violated:
            violations.append({"metric": t.metric, "value": value, "threshold": t.threshold, "severity": t.severity})
    return violations


async def update_regression_threshold(db: AsyncSession, threshold_id: uuid.UUID, data: dict) -> RegressionThreshold | None:
    """Item 2's own literal function -- real, partial update (only
    real, explicitly-given keys change). Honestly `None` for an
    unknown threshold."""
    row = await db.get(RegressionThreshold, threshold_id)
    if row is None:
        return None
    for key in ("threshold", "severity", "enabled"):
        if key in data:
            setattr(row, key, data[key])
    await db.flush()
    return row


async def delete_regression_threshold(db: AsyncSession, threshold_id: uuid.UUID) -> bool:
    """Item 2's own literal function -- honestly `False` for an
    unknown threshold, never a silent no-op success."""
    row = await db.get(RegressionThreshold, threshold_id)
    if row is None:
        return False
    await db.delete(row)
    await db.flush()
    return True
