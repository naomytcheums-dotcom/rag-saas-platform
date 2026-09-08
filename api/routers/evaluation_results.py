"""
Partie 7.2.1 -- real evaluation-run endpoints. Every real route
resolves its own resource AND the caller's real Admin+ role together
(`api/security/evaluation.py`'s own `require_question_admin`/
`require_dataset_admin`), same real "les permissions sont respectées"
criterion every one of this batch's own 9 étapes lists."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.organization import OrganizationMember
from api.schemas.evaluation import (
    EvaluationResultListResponse, EvaluationResultResponse, LatencyMeasurementResponse, MetricsSummaryResponse,
    RunEvaluationRequest,
)
from api.security.evaluation import require_dataset_admin, require_question_admin
from api.services.evaluation_results import get_evaluation_results, get_metrics_summary, run_evaluation
from api.services.latency_metrics import measure_latency

router = APIRouter(tags=["evaluation-results"])


@router.post("/questions/{question_id}/run", response_model=EvaluationResultResponse, status_code=status.HTTP_201_CREATED)
async def run_evaluation_endpoint(
    payload: RunEvaluationRequest = RunEvaluationRequest(),
    question_ctx: tuple[EvaluationQuestion, OrganizationMember] = Depends(require_question_admin), db: AsyncSession = Depends(get_db),
):
    question, _caller = question_ctx
    result = await run_evaluation(db, question.id, agent_id=payload.agent_id, model_config=payload.model_config_override)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return result


@router.get("/questions/{question_id}/results", response_model=EvaluationResultListResponse)
async def get_evaluation_results_endpoint(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    question_ctx: tuple[EvaluationQuestion, OrganizationMember] = Depends(require_question_admin), db: AsyncSession = Depends(get_db),
):
    question, _caller = question_ctx
    return await get_evaluation_results(db, question.id, limit, offset)


@router.get("/datasets/{dataset_id}/metrics/{metric}", response_model=MetricsSummaryResponse)
async def get_metrics_summary_endpoint(
    metric: str, dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin),
    db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await get_metrics_summary(db, dataset.id, metric)


@router.post("/questions/{question_id}/latency", response_model=LatencyMeasurementResponse, status_code=status.HTTP_201_CREATED)
async def measure_latency_endpoint(
    payload: RunEvaluationRequest = RunEvaluationRequest(),
    question_ctx: tuple[EvaluationQuestion, OrganizationMember] = Depends(require_question_admin), db: AsyncSession = Depends(get_db),
):
    """Partie 7.2.13's own dedicated benchmark endpoint -- every other
    real Partie 7.2.10-7.2.15 metric is already surfaced through the
    existing `POST /questions/{id}/run` (its own `metrics` dict) and
    `GET /datasets/{id}/metrics/{metric}` (already generic over ANY
    real, flat metric key -- `context_relevance`/`citation_correctness`/
    `hallucination_rate`/`cost_per_request`/`total_tokens` all just
    work there already, no new dedicated endpoint needed). Latency is
    the one real exception: its own real signal is a real, MULTI-RUN
    distribution, not a single stored result."""
    question, _caller = question_ctx
    result = await measure_latency(db, question.id, agent_id=payload.agent_id, model_config=payload.model_config_override)
    await db.commit()
    return result
