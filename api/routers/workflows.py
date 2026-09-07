"""
Partie 5.4.1 -- real workflow CRUD + structural validation. Create/list
are org-scoped and Manager+ (item 5's own literal tier -- unlike
Partie 5.3.1's agents, list is NOT Member+ here); get/update/delete/
validate resolve the workflow AND the caller's real organization role
together (`require_workflow_member`/`require_workflow_manager`),
same reasoning as `api/routers/agents.py`.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.models.workflow import Workflow
from api.schemas.workflows import (
    WorkflowCreateRequest, WorkflowResponse, WorkflowUpdateRequest, WorkflowValidateResponse,
)
from api.security.organizations import require_org_manager
from api.security.workflows import (
    create_workflow, delete_workflow, list_workflows, require_workflow_manager, require_workflow_member,
    update_workflow,
)
from api.services.workflows import WorkflowValidationError, validate_workflow

router = APIRouter(tags=["workflows"])


@router.post("/organizations/{org_id}/workflows", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_endpoint(
    org_id: uuid.UUID, payload: WorkflowCreateRequest,
    caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    try:
        workflow = await create_workflow(db, org_id, payload.model_dump(), caller.user_id)
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.get("/organizations/{org_id}/workflows", response_model=list[WorkflowResponse])
async def list_workflows_endpoint(
    org_id: uuid.UUID, limit: int = Query(default=50, le=200), offset: int = Query(default=0, ge=0),
    _caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    return await list_workflows(db, org_id, limit=limit, offset=offset)


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow_endpoint(workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_member)):
    workflow, _caller = workflow_ctx
    return workflow


@router.patch("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow_endpoint(
    payload: WorkflowUpdateRequest,
    workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_manager), db: AsyncSession = Depends(get_db),
):
    workflow, _caller = workflow_ctx
    try:
        updated = await update_workflow(db, workflow.id, payload.model_dump(exclude_unset=True))
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(updated)
    return updated


@router.delete("/workflows/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_endpoint(
    workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_manager), db: AsyncSession = Depends(get_db),
):
    workflow, _caller = workflow_ctx
    await delete_workflow(db, workflow.id)
    await db.commit()


@router.post("/workflows/{workflow_id}/validate", response_model=WorkflowValidateResponse)
async def validate_workflow_endpoint(workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_manager)):
    workflow, _caller = workflow_ctx
    errors = validate_workflow(workflow.nodes, workflow.edges)
    return WorkflowValidateResponse(valid=len(errors) == 0, errors=errors)
