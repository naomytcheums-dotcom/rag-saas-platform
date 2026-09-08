"""Partie 7.3.2 -- manual (human) evaluation endpoints. Member+
(excluding Viewer) for creating/reading/updating a real evaluation;
Admin+ for real, dataset-wide stats (`require_dataset_admin`, same
tier as every other real dataset-scoped Evaluation Lab endpoint)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.evaluation import EvaluationDataset, EvaluationQuestion, ManualEvaluation
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.schemas.evaluation import (
    ManualEvaluationCreateRequest, ManualEvaluationListResponse, ManualEvaluationResponse, ManualEvaluationStatsResponse,
    ManualEvaluationSummaryResponse, ManualEvaluationUpdateRequest,
)
from api.security.evaluation import require_dataset_admin, require_manual_evaluation_access, require_question_member
from api.services.manual_evaluations import (
    create_manual_evaluation, get_manual_evaluation_stats, get_manual_evaluation_summary, list_manual_evaluations,
    update_manual_evaluation,
)

router = APIRouter(tags=["manual-evaluations"])


@router.post("/questions/{question_id}/evaluate", response_model=ManualEvaluationResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_evaluation_endpoint(
    payload: ManualEvaluationCreateRequest, question_ctx: tuple[EvaluationQuestion, OrganizationMember] = Depends(require_question_member),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    question, _caller = question_ctx
    try:
        evaluation = await create_manual_evaluation(
            db, question.id, payload.agent_id, current_user.id, payload.score, payload.feedback, payload.criteria,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(evaluation)
    return evaluation


@router.get("/questions/{question_id}/evaluations", response_model=ManualEvaluationListResponse)
async def list_manual_evaluations_endpoint(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    question_ctx: tuple[EvaluationQuestion, OrganizationMember] = Depends(require_question_member), db: AsyncSession = Depends(get_db),
):
    question, _caller = question_ctx
    return await list_manual_evaluations(db, question.id, limit, offset)


@router.get("/questions/{question_id}/evaluations/summary", response_model=ManualEvaluationSummaryResponse)
async def get_manual_evaluation_summary_endpoint(
    question_ctx: tuple[EvaluationQuestion, OrganizationMember] = Depends(require_question_member), db: AsyncSession = Depends(get_db),
):
    question, _caller = question_ctx
    return await get_manual_evaluation_summary(db, question.id)


@router.get("/evaluations/{evaluation_id}", response_model=ManualEvaluationResponse)
async def get_manual_evaluation_endpoint(
    evaluation_ctx: tuple[ManualEvaluation, OrganizationMember] = Depends(require_manual_evaluation_access),
):
    evaluation, _caller = evaluation_ctx
    return evaluation


@router.patch("/evaluations/{evaluation_id}", response_model=ManualEvaluationResponse)
async def update_manual_evaluation_endpoint(
    payload: ManualEvaluationUpdateRequest, evaluation_ctx: tuple[ManualEvaluation, OrganizationMember] = Depends(require_manual_evaluation_access),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Item 4's own literal "Member+ si propriétaire" -- the real
    ownership check (`evaluator_id == current_user.id`) OR real Admin+
    lives here, one real layer above `require_manual_evaluation_access`'s
    own base real Member+ resolution (same real, deliberate split as
    every other dependency in `api/security/evaluation.py`)."""
    evaluation, caller = evaluation_ctx
    is_owner = evaluation.evaluator_id == current_user.id
    is_admin = caller.role in (OrganizationRole.owner, OrganizationRole.admin)
    if not is_owner and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the evaluator or an org admin can modify this evaluation")
    try:
        updated = await update_manual_evaluation(db, evaluation.id, payload.score, payload.feedback, payload.criteria)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(updated)
    return updated


@router.get("/datasets/{dataset_id}/evaluations/stats", response_model=ManualEvaluationStatsResponse)
async def get_manual_evaluation_stats_endpoint(
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await get_manual_evaluation_stats(db, dataset.id)
