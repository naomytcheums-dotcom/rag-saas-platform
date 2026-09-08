"""
Partie 7.1.2 -- real question-set endpoints. `POST/GET /datasets/{dataset_id}/sets`
reuse `require_dataset_admin` (Partie 7.1.1); every other real route
resolves the set itself AND the caller's real Admin+ role together
(`api/security/evaluation.py`'s own `require_question_set_admin`)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.evaluation import EvaluationDataset, QuestionSet
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.evaluation import (
    AddQuestionToSetRequest, DuplicateQuestionSetRequest, QuestionResponse, QuestionSetCreateRequest,
    QuestionSetListResponse, QuestionSetResponse, QuestionSetUpdateRequest, ReorderQuestionsRequest,
)
from api.security.evaluation import require_dataset_admin, require_question_set_admin
from api.services.question_sets import (
    add_question_to_set, create_question_set, delete_question_set, duplicate_question_set, get_questions_in_set,
    list_question_sets, remove_question_from_set, reorder_questions, update_question_set,
)

router = APIRouter(tags=["question-sets"])


@router.post("/datasets/{dataset_id}/sets", response_model=QuestionSetResponse, status_code=status.HTTP_201_CREATED)
async def create_question_set_endpoint(
    payload: QuestionSetCreateRequest, current_user: User = Depends(get_current_user),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    question_set = await create_question_set(db, dataset.id, payload.name, payload.description, current_user.id)
    await db.commit()
    return question_set


@router.get("/datasets/{dataset_id}/sets", response_model=QuestionSetListResponse)
async def list_question_sets_endpoint(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    return await list_question_sets(db, dataset.id, limit, offset)


@router.get("/sets/{set_id}", response_model=QuestionSetResponse)
async def get_question_set_endpoint(set_ctx: tuple[QuestionSet, OrganizationMember] = Depends(require_question_set_admin)):
    question_set, _caller = set_ctx
    return question_set


@router.patch("/sets/{set_id}", response_model=QuestionSetResponse)
async def update_question_set_endpoint(
    payload: QuestionSetUpdateRequest, set_ctx: tuple[QuestionSet, OrganizationMember] = Depends(require_question_set_admin),
    db: AsyncSession = Depends(get_db),
):
    question_set, _caller = set_ctx
    updated = await update_question_set(db, question_set.id, payload.name, payload.description)
    await db.commit()
    return updated


@router.delete("/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question_set_endpoint(
    set_ctx: tuple[QuestionSet, OrganizationMember] = Depends(require_question_set_admin), db: AsyncSession = Depends(get_db),
):
    question_set, _caller = set_ctx
    await delete_question_set(db, question_set.id)
    await db.commit()


@router.post("/sets/{set_id}/questions", status_code=status.HTTP_201_CREATED)
async def add_question_to_set_endpoint(
    payload: AddQuestionToSetRequest, set_ctx: tuple[QuestionSet, OrganizationMember] = Depends(require_question_set_admin),
    db: AsyncSession = Depends(get_db),
):
    question_set, _caller = set_ctx
    item = await add_question_to_set(db, question_set.id, payload.question_id, payload.position)
    await db.commit()
    return {"question_set_id": item.question_set_id, "question_id": item.question_id, "position": item.position}


@router.delete("/sets/{set_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_question_from_set_endpoint(
    question_id: uuid.UUID, set_ctx: tuple[QuestionSet, OrganizationMember] = Depends(require_question_set_admin),
    db: AsyncSession = Depends(get_db),
):
    question_set, _caller = set_ctx
    await remove_question_from_set(db, question_set.id, question_id)
    await db.commit()


@router.patch("/sets/{set_id}/questions/reorder", response_model=list[QuestionResponse])
async def reorder_questions_endpoint(
    payload: ReorderQuestionsRequest, set_ctx: tuple[QuestionSet, OrganizationMember] = Depends(require_question_set_admin),
    db: AsyncSession = Depends(get_db),
):
    question_set, _caller = set_ctx
    try:
        await reorder_questions(db, question_set.id, payload.question_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return await get_questions_in_set(db, question_set.id)


@router.post("/sets/{set_id}/duplicate", response_model=QuestionSetResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_question_set_endpoint(
    payload: DuplicateQuestionSetRequest, current_user: User = Depends(get_current_user),
    set_ctx: tuple[QuestionSet, OrganizationMember] = Depends(require_question_set_admin), db: AsyncSession = Depends(get_db),
):
    question_set, _caller = set_ctx
    duplicate = await duplicate_question_set(db, question_set.id, payload.new_name, current_user.id)
    await db.commit()
    return duplicate
