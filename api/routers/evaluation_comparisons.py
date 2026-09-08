"""
Partie 7.3 -- multi-model comparison and A/B-test endpoints, scoped by
a real `QuestionSet` (see `api/services/evaluation_comparisons.py`'s
own docstring for why). Both real routes resolve the set itself AND
the caller's real Admin+ role together, reusing
`api/security/evaluation.py`'s own `require_question_set_admin`
directly -- the SAME real dependency `api/routers/question_sets.py`
already uses for every other real `/sets/{set_id}/...` route."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.evaluation import QuestionSet
from api.models.organization import OrganizationMember
from api.schemas.evaluation import ABTestRequest, ABTestResponse, MultiModelComparisonRequest, MultiModelComparisonResponse
from api.security.evaluation import require_question_set_admin
from api.services.evaluation_comparisons import run_ab_test, run_multi_model_comparison

router = APIRouter(tags=["evaluation-comparisons"])


@router.post("/sets/{set_id}/compare", response_model=MultiModelComparisonResponse, status_code=status.HTTP_201_CREATED)
async def run_multi_model_comparison_endpoint(
    payload: MultiModelComparisonRequest, set_ctx: tuple[QuestionSet, OrganizationMember] = Depends(require_question_set_admin),
    db: AsyncSession = Depends(get_db),
):
    question_set, _caller = set_ctx
    comparison = await run_multi_model_comparison(db, question_set.id, payload.model_configs)
    await db.commit()
    return comparison


@router.post("/sets/{set_id}/ab-test", response_model=ABTestResponse, status_code=status.HTTP_201_CREATED)
async def run_ab_test_endpoint(
    payload: ABTestRequest, set_ctx: tuple[QuestionSet, OrganizationMember] = Depends(require_question_set_admin),
    db: AsyncSession = Depends(get_db),
):
    question_set, _caller = set_ctx
    result = await run_ab_test(db, question_set.id, payload.model_config_a, payload.model_config_b, payload.metric)
    await db.commit()
    return result
