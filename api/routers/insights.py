"""Specs 11.2.x and 15.2.x -- usage insights for the organization's staff (manager role): most asked / failed questions, question clusters,
knowledge and documentation gaps, most and least useful documents, retrieval success rate, live-feedback failure analysis and
feedback-to-evaluation-cases. Read-only except `feedback/to-evaluation`, which writes evaluation questions and therefore needs the admin role."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.security.organizations import require_org_admin, require_org_manager
from api.services import insights

router = APIRouter(tags=["insights"])

_DAYS = Query(default=30, ge=1, le=365)


class FeedbackToEvaluationRequest(BaseModel):
    dataset_id: uuid.UUID
    only_with_correction: bool = False


@router.get("/organizations/{org_id}/insights/most-asked")
async def most_asked_questions(org_id: uuid.UUID, days: int = _DAYS, limit: int = Query(default=10, ge=1, le=100), _c: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    return {"items": insights.most_asked(await insights.load_question_answer_pairs(db, org_id, days), limit)}


@router.get("/organizations/{org_id}/insights/failed-questions")
async def failed_questions(org_id: uuid.UUID, days: int = _DAYS, _c: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    return {"items": insights.failed_questions(await insights.load_question_answer_pairs(db, org_id, days))}


@router.get("/organizations/{org_id}/insights/retrieval-success")
async def retrieval_success(org_id: uuid.UUID, days: int = _DAYS, _c: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    return insights.retrieval_success_rate(await insights.load_question_answer_pairs(db, org_id, days))


@router.get("/organizations/{org_id}/insights/question-clusters")
async def question_clusters(org_id: uuid.UUID, days: int = _DAYS, _c: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    pairs = await insights.load_question_answer_pairs(db, org_id, days)
    return {"items": insights.cluster_questions([p["question"] for p in pairs])[:50]}


@router.get("/organizations/{org_id}/insights/knowledge-gaps")
async def knowledge_gaps(org_id: uuid.UUID, days: int = _DAYS, min_count: int = Query(default=2, ge=1, le=100), _c: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    return {"items": insights.knowledge_gaps(await insights.load_question_answer_pairs(db, org_id, days), min_count)}


@router.get("/organizations/{org_id}/insights/documentation-gaps")
async def documentation_gaps(org_id: uuid.UUID, days: int = _DAYS, min_count: int = Query(default=2, ge=1, le=100), _c: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    pairs = await insights.load_question_answer_pairs(db, org_id, days)
    return {"items": await insights.documentation_gap_report(db, org_id, pairs, min_count)}


@router.get("/organizations/{org_id}/insights/documents/top")
async def top_documents(org_id: uuid.UUID, days: int = _DAYS, limit: int = Query(default=10, ge=1, le=100), _c: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    return {"items": insights.top_documents(await insights.document_usage(db, org_id, days), limit)}


@router.get("/organizations/{org_id}/insights/documents/worst")
async def worst_documents(org_id: uuid.UUID, days: int = _DAYS, limit: int = Query(default=10, ge=1, le=100), _c: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    return {"items": insights.worst_documents(await insights.document_usage(db, org_id, days), limit)}


@router.get("/organizations/{org_id}/insights/cost-per-user")
async def cost_per_user(org_id: uuid.UUID, days: int = _DAYS, _c: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    return {"items": await insights.cost_per_user(db, org_id, days)}


@router.get("/organizations/{org_id}/insights/cost-per-answer")
async def cost_per_answer(org_id: uuid.UUID, days: int = _DAYS, _c: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    return await insights.cost_per_answer(db, org_id, days)


@router.get("/organizations/{org_id}/feedback/analysis")
async def feedback_analysis(org_id: uuid.UUID, days: int = Query(default=90, ge=1, le=365), _c: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db)):
    return await insights.feedback_failure_analysis(db, org_id, days)


@router.post("/organizations/{org_id}/feedback/to-evaluation")
async def feedback_to_evaluation(org_id: uuid.UUID, payload: FeedbackToEvaluationRequest, days: int = Query(default=90, ge=1, le=365), _c: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        result = await insights.feedback_to_evaluation_cases(db, org_id, payload.dataset_id, payload.only_with_correction, days)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    await db.commit()
    return result
