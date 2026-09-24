"""
Partie 7.1.1 -- real dataset/question management endpoints. The 2
top-level routes carry `{org_id}` (Admin+, `require_org_admin`, same
as `api/routers/usage.py`); every other real route resolves the
resource AND the caller's real Admin+ role together
(`api/security/evaluation.py`'s own `require_dataset_admin`/
`require_question_admin`)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.evaluation import (
    DatasetCreateRequest, DatasetListResponse, DatasetResponse, DatasetUpdateRequest, QuestionCreateRequest,
    QuestionImportResponse, QuestionListResponse, QuestionResponse, QuestionUpdateRequest,
)
from api.security.permissions import require_permission
from api.security.evaluation import require_dataset_admin, require_question_admin
from api.security.organizations import require_org_admin
from api.services.evaluation_datasets import (
    add_question, create_dataset, delete_dataset, delete_question, export_questions, get_questions, import_questions,
    list_datasets, update_dataset, update_question,
)

router = APIRouter(tags=["evaluation-datasets"])


@router.post("/organizations/{org_id}/datasets", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset_endpoint(
    org_id: uuid.UUID, payload: DatasetCreateRequest, current_user: User = Depends(get_current_user),
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    dataset = await create_dataset(db, org_id, payload.name, payload.description, current_user.id)
    await db.commit()
    return dataset


@router.get("/organizations/{org_id}/datasets", response_model=DatasetListResponse)
async def list_datasets_endpoint(
    org_id: uuid.UUID, is_active: bool | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    filters = {"is_active": is_active} if is_active is not None else None
    return await list_datasets(db, org_id, filters, limit, offset)


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset_endpoint(dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin)):
    dataset, _caller = dataset_ctx
    return dataset


@router.patch("/datasets/{dataset_id}", response_model=DatasetResponse)
async def update_dataset_endpoint(
    payload: DatasetUpdateRequest, dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin),
    db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    updated = await update_dataset(db, dataset.id, payload.name, payload.description, payload.is_active)
    await db.commit()
    return updated


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset_endpoint(
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    await delete_dataset(db, dataset.id)
    await db.commit()


@router.post("/datasets/{dataset_id}/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def add_question_endpoint(
    payload: QuestionCreateRequest, dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin),
    db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    question = await add_question(
        db, dataset.id, payload.question, payload.expected_answer, payload.expected_documents,
        payload.difficulty, payload.category,
    )
    await db.commit()
    return question


@router.get("/datasets/{dataset_id}/questions", response_model=QuestionListResponse)
async def get_questions_endpoint(
    difficulty: str | None = None, category: str | None = None,
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    filters = {"difficulty": difficulty, "category": category}
    return await get_questions(db, dataset.id, filters, limit, offset)


@router.patch("/questions/{question_id}", response_model=QuestionResponse)
async def update_question_endpoint(
    payload: QuestionUpdateRequest, question_ctx: tuple[EvaluationQuestion, OrganizationMember] = Depends(require_question_admin),
    db: AsyncSession = Depends(get_db),
):
    question, _caller = question_ctx
    updated = await update_question(db, question.id, payload.model_dump(exclude_unset=True))
    await db.commit()
    return updated


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question_endpoint(
    question_ctx: tuple[EvaluationQuestion, OrganizationMember] = Depends(require_question_admin), db: AsyncSession = Depends(get_db),
):
    question, _caller = question_ctx
    await delete_question(db, question.id)
    await db.commit()


@router.post("/datasets/{dataset_id}/questions/import", response_model=QuestionImportResponse)
async def import_questions_endpoint(
    file: UploadFile, format: str = Query(default="json", pattern="^(json|csv)$"),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    content = await file.read()
    try:
        result = await import_questions(db, dataset.id, content, format)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return result


@router.get("/datasets/{dataset_id}/questions/export")
async def export_questions_endpoint(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    dataset_ctx: tuple[EvaluationDataset, OrganizationMember] = Depends(require_dataset_admin), db: AsyncSession = Depends(get_db),
):
    dataset, _caller = dataset_ctx
    content = await export_questions(db, dataset.id, format)
    if format == "csv":
        return Response(
            content=content, media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=questions-{dataset.id}.csv"},
        )
    return Response(
        content=content, media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=questions-{dataset.id}.json"},
    )
