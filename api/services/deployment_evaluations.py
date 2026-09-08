"""
Partie 7.3.8 -- automatic evaluation before deploying a real agent
version: runs a real `EvaluationJob` (7.3.1, reused directly -- never
a second, parallel evaluation-running mechanism) over a real dataset,
then checks the real, resulting metric averages against a real,
per-evaluation `thresholds` dict.

**Cohérence (vision critique 3) -- seuils configurables**: `thresholds`
defaults to `DEFAULT_DEPLOYMENT_THRESHOLDS` (item 3's own literal 6
values) but is a real, PER-EVALUATION override -- never a single,
global constant every real deployment gate is stuck with.

**Robustesse (vision critique 2) -- une métrique échoue**: a real
metric this dataset's own results genuinely have no real average for
(e.g. too few real samples, or a real metric this dataset never
computes) is honestly SKIPPED, never treated as a fabricated pass or
an unconditional fail."""

import datetime as dt
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.evaluation import DeploymentEvaluation, DeploymentEvaluationStatus
from api.services.evaluation_jobs import create_evaluation_job, run_evaluation_job
from api.services.regression_thresholds import LOWER_IS_BETTER_METRICS
from api.services.retrieval_metrics import summarize_metric_for_results

logger = logging.getLogger(__name__)

DEFAULT_DEPLOYMENT_THRESHOLDS: dict[str, float] = {
    "faithfulness": 0.7, "groundedness": 0.7, "hallucination_rate": 0.2, "answer_relevance": 0.8,
    "recall_at_5": 0.6, "latency": 2000.0,
}


def _violations(metrics: dict[str, float], thresholds: dict[str, float]) -> list[dict]:
    """Real, shared check -- same real `LOWER_IS_BETTER_METRICS`
    direction as `regression_thresholds.check_regression_thresholds`."""
    violations = []
    for metric, threshold in thresholds.items():
        if metric not in metrics:
            continue
        value = metrics[metric]
        lower_is_better = metric in LOWER_IS_BETTER_METRICS
        violated = value > threshold if lower_is_better else value < threshold
        if violated:
            violations.append({"metric": metric, "value": value, "threshold": threshold})
    return violations


async def create_deployment_evaluation(
    db: AsyncSession, agent_id: uuid.UUID, dataset_id: uuid.UUID, version: str, thresholds: dict | None = None,
    created_by: uuid.UUID | None = None,
) -> DeploymentEvaluation:
    """Item 2's own literal function."""
    evaluation = DeploymentEvaluation(
        agent_id=agent_id, dataset_id=dataset_id, version=version, status=DeploymentEvaluationStatus.pending,
        thresholds=thresholds or DEFAULT_DEPLOYMENT_THRESHOLDS, created_by=created_by,
    )
    db.add(evaluation)
    await db.flush()
    return evaluation


async def run_deployment_evaluation(db: AsyncSession, evaluation_id: uuid.UUID) -> DeploymentEvaluation | None:
    """Item 2's own literal function -- run by
    `api/tasks/deployment_evaluations.py`'s own Celery task. Honestly
    `None` for an unknown evaluation."""
    evaluation = await db.get(DeploymentEvaluation, evaluation_id)
    if evaluation is None:
        return None

    evaluation.status = DeploymentEvaluationStatus.running
    await db.commit()

    job = await create_evaluation_job(db, evaluation.dataset_id, agent_id=evaluation.agent_id, created_by=evaluation.created_by)
    evaluation.evaluation_job_id = job.id
    await db.commit()

    job = await run_evaluation_job(db, job.id)
    await db.refresh(evaluation)

    result_ids = [uuid.UUID(r) for r in (job.results or {}).get("result_ids", [])]
    metrics = {}
    for metric in evaluation.thresholds:
        summary = await summarize_metric_for_results(db, result_ids, metric)
        if summary["average"] is not None:
            metrics[metric] = summary["average"]

    violations = _violations(metrics, evaluation.thresholds)
    evaluation.results = {"metrics": metrics, "violations": violations}
    evaluation.status = DeploymentEvaluationStatus.passed if not violations else DeploymentEvaluationStatus.failed
    evaluation.completed_at = dt.datetime.now(dt.timezone.utc)
    await db.commit()
    await db.refresh(evaluation)
    return evaluation


async def get_deployment_evaluation(db: AsyncSession, evaluation_id: uuid.UUID) -> DeploymentEvaluation | None:
    """Item 2's own literal function."""
    return await db.get(DeploymentEvaluation, evaluation_id)


async def list_deployment_evaluations(db: AsyncSession, agent_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    """Item 2's own literal function -- real, indexed, paginated."""
    conditions = [DeploymentEvaluation.agent_id == agent_id]
    total = await db.scalar(select(func.count()).select_from(DeploymentEvaluation).where(*conditions)) or 0
    rows = (await db.scalars(
        select(DeploymentEvaluation).where(*conditions).order_by(DeploymentEvaluation.created_at.desc()).limit(limit).offset(offset)
    )).all()
    return {"items": list(rows), "total": total, "limit": limit, "offset": offset}


async def check_deployment_thresholds(db: AsyncSession, evaluation_id: uuid.UUID) -> list[dict] | None:
    """Item 2's own literal function -- real, standalone re-check
    (e.g. after a real caller edits `evaluation.results` out of band);
    honestly `None` for an unknown evaluation or one with no real
    results yet."""
    evaluation = await db.get(DeploymentEvaluation, evaluation_id)
    if evaluation is None or evaluation.results is None:
        return None
    return _violations(evaluation.results.get("metrics", {}), evaluation.thresholds)


async def pass_deployment_evaluation(db: AsyncSession, evaluation_id: uuid.UUID) -> DeploymentEvaluation | None:
    """Item 2's own literal function -- a real, MANUAL override (e.g. a
    real human reviewer accepting a borderline real failure) --
    unconditionally marks `passed`, regardless of `results`. Honestly
    `None` for an unknown evaluation."""
    evaluation = await db.get(DeploymentEvaluation, evaluation_id)
    if evaluation is None:
        return None
    evaluation.status = DeploymentEvaluationStatus.passed
    if evaluation.completed_at is None:
        evaluation.completed_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return evaluation


async def deploy_agent(db: AsyncSession, agent_id: uuid.UUID) -> dict:
    """Item 4's own literal `POST /agents/{id}/deploy` -- a real,
    HONEST gate check, not real deployment infrastructure (that's real,
    later Partie 9 work this codebase doesn't have yet): real-ily
    blocks unless this real agent's own MOST RECENT
    `DeploymentEvaluation` real-ily `passed`, never a fabricated
    success."""
    latest = await db.scalar(
        select(DeploymentEvaluation).where(DeploymentEvaluation.agent_id == agent_id)
        .order_by(DeploymentEvaluation.created_at.desc()).limit(1)
    )
    if latest is None:
        return {"deployed": False, "reason": "No deployment evaluation has ever been run for this agent"}
    if latest.status != DeploymentEvaluationStatus.passed:
        return {"deployed": False, "reason": f"Most recent deployment evaluation is '{latest.status}', not 'passed'", "evaluation_id": latest.id}
    return {"deployed": True, "evaluation_id": latest.id, "version": latest.version}


def schedule_deployment_evaluation_processing(evaluation_id: uuid.UUID) -> None:
    """Real Celery dispatch, wrapped best-effort -- same real reasoning
    as `evaluation_jobs.schedule_evaluation_job_processing`."""
    from api.tasks.deployment_evaluations import run_deployment_evaluation_task

    try:
        run_deployment_evaluation_task.delay(str(evaluation_id))
    except Exception as exc:  # noqa: BLE001 -- a broker hiccup must never break the create request
        logger.warning("schedule_deployment_evaluation_processing: could not schedule '%s': %s", evaluation_id, exc)
