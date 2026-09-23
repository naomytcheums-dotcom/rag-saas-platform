"""
Partie 5.4.1 -- real workflow CRUD + structural validation. Create/list
are org-scoped and Manager+ (item 5's own literal tier -- unlike
Partie 5.3.1's agents, list is NOT Member+ here); get/update/delete/
validate resolve the workflow AND the caller's real organization role
together (`require_workflow_member`/`require_workflow_manager`),
same reasoning as `api/routers/agents.py`.
"""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.models.workflow import Workflow
from api.models.workflow_run import WorkflowRun
from api.schemas.workflow_human_input import WorkflowHumanInputResponse, WorkflowHumanInputSubmitRequest
from api.schemas.workflow_triggers import (
    WorkflowRunRequest, WorkflowRunResponse, WorkflowTriggerCreateRequest, WorkflowTriggerResponse,
)
from api.schemas.workflow_versions import (
    WorkflowVersionCreateRequest, WorkflowVersionDiffRequest, WorkflowVersionDiffResponse,
    WorkflowVersionRestoreRequest, WorkflowVersionResponse,
)
from api.schemas.workflows import (
    WorkflowCreateRequest, WorkflowResponse, WorkflowUpdateRequest, WorkflowValidateResponse,
)
from api.security.organizations import require_org_manager
from api.security.workflows import (
    create_workflow, delete_workflow, import_workflow, list_workflow_runs, list_workflows, require_workflow_manager,
    require_workflow_member, require_workflow_run_member, update_workflow,
)
from api.services.workflow_block_human import get_human_approval, list_human_blocks, submit_human_input
from api.services.workflow_blocks import WorkflowBlockError
from api.services.workflow_engine import stream_workflow_run
from api.tasks.workflows import schedule_workflow_resume, schedule_workflow_run
from api.utils import MAX_PAGE_SIZE
from api.services.workflow_triggers import (
    TRIGGER_TYPES, WorkflowTriggerError, create_manual_trigger, create_schedule_trigger, create_webhook_trigger,
    delete_trigger, get_trigger, list_triggers, trigger_workflow, verify_webhook_token,
)
from api.services.workflow_versions import (
    WorkflowVersionError, create_workflow_version, diff_workflow_versions, get_workflow_version,
    list_workflow_versions, restore_workflow_version,
)
from api.services.workflows import WorkflowValidationError, export_workflow, validate_workflow

router = APIRouter(tags=["workflows"])
_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


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


# Phase 5, Étape 5 -- real gap found during this étape's own audit:
# api/security/workflows.import_workflow and
# api/services/workflows.export_workflow were real, complete,
# tested-in-isolation functions with ZERO router endpoint anywhere --
# the same "built, never wired" pattern this session has found and
# closed before (billing_stripe_sync.py, Phase 5 Étape 3). Org-scoped,
# not the literal spec's flat `/workflows/import`/`GET /workflows/{id}/export`
# paths -- this codebase's own real, established convention for
# anything that creates a NEW org-owned resource
# (`/organizations/{org_id}/workflows`, same router, right above).

@router.post("/organizations/{org_id}/workflows/import", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def import_workflow_endpoint(
    org_id: uuid.UUID, payload: WorkflowCreateRequest,
    caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    try:
        workflow = await import_workflow(db, org_id, payload.model_dump(), caller.user_id)
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.get("/workflows/{workflow_id}/export")
async def export_workflow_endpoint(workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_member)):
    workflow, _caller = workflow_ctx
    return export_workflow(workflow)


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


# ------------------------------------- Partie 5.4.2 -- triggers -------------------------------------


@router.post("/workflows/{workflow_id}/triggers", response_model=WorkflowTriggerResponse)
async def create_trigger_endpoint(
    payload: WorkflowTriggerCreateRequest,
    workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_manager), db: AsyncSession = Depends(get_db),
):
    workflow, _caller = workflow_ctx
    try:
        if payload.type == "webhook":
            trigger = await create_webhook_trigger(db, workflow.id, payload.config)
        elif payload.type == "schedule":
            trigger = await create_schedule_trigger(db, workflow.id, payload.config.get("cron_pattern", ""))
        elif payload.type == "manual":
            trigger = await create_manual_trigger(db, workflow.id)
        else:
            raise WorkflowTriggerError(f"Unknown trigger type: {payload.type!r} (expected one of {TRIGGER_TYPES})")
    except WorkflowTriggerError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return trigger


@router.get("/workflows/{workflow_id}/triggers", response_model=list[WorkflowTriggerResponse])
async def list_triggers_endpoint(
    workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_manager), db: AsyncSession = Depends(get_db),
):
    workflow, _caller = workflow_ctx
    return await list_triggers(db, workflow.id)


@router.delete("/workflows/{workflow_id}/triggers/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trigger_endpoint(
    trigger_id: uuid.UUID,
    workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_manager), db: AsyncSession = Depends(get_db),
):
    workflow, _caller = workflow_ctx
    trigger = await get_trigger(db, trigger_id)
    if trigger is not None and trigger.workflow_id == workflow.id:
        await delete_trigger(db, trigger_id)
        await db.commit()


@router.post("/webhooks/{trigger_id}", response_model=WorkflowRunResponse)
async def run_workflow_via_webhook_endpoint(
    trigger_id: uuid.UUID, payload: WorkflowRunRequest,
    x_webhook_token: str = Header(..., alias="X-Webhook-Token"), db: AsyncSession = Depends(get_db),
):
    trigger = await get_trigger(db, trigger_id)
    if trigger is None or trigger.type != "webhook" or not verify_webhook_token(trigger, x_webhook_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook token")
    run = await trigger_workflow(db, trigger.workflow_id, payload.input, trigger_id=trigger.id)
    await db.commit()
    schedule_workflow_run(run.id)
    return run


@router.post("/workflows/{workflow_id}/run", response_model=WorkflowRunResponse)
async def run_workflow_manually_endpoint(
    payload: WorkflowRunRequest,
    workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_member), db: AsyncSession = Depends(get_db),
):
    workflow, _caller = workflow_ctx
    run = await trigger_workflow(db, workflow.id, payload.input)
    await db.commit()
    schedule_workflow_run(run.id)
    return run


# ------------------------------------- Phase 5, Étape 5 -- execution history + live debug -------------------------------------
# Real gap found during this étape's own audit: POST .../run existed,
# but nothing ever listed a workflow's own past runs, fetched one run's
# own detail, or streamed a running one live -- all three genuinely
# required by the Workflow Builder UI's own execution-history and
# debug/run panels (this étape's own spec, sections 3.4/3.5), not
# optional.

@router.get("/workflows/{workflow_id}/runs", response_model=list[WorkflowRunResponse])
async def list_workflow_runs_endpoint(
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0),
    workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_member), db: AsyncSession = Depends(get_db),
):
    workflow, _caller = workflow_ctx
    return await list_workflow_runs(db, workflow.id, limit, offset)


@router.get("/workflows/runs/{run_id}", response_model=WorkflowRunResponse)
async def get_workflow_run_endpoint(run_ctx: tuple[WorkflowRun, OrganizationMember] = Depends(require_workflow_run_member)):
    run, _caller = run_ctx
    return run


@router.get("/workflows/runs/{run_id}/stream")
async def stream_workflow_run_endpoint(run_ctx: tuple[WorkflowRun, OrganizationMember] = Depends(require_workflow_run_member)) -> StreamingResponse:
    run, _caller = run_ctx
    return StreamingResponse(stream_workflow_run(run), media_type="text/event-stream", headers=_SSE_HEADERS)


# ------------------------------------- Partie 5.4.9 -- human block -------------------------------------


@router.get("/workflows/runs/{run_id}/human-blocks", response_model=list[WorkflowHumanInputResponse])
async def list_human_blocks_endpoint(
    run_ctx: tuple[WorkflowRun, OrganizationMember] = Depends(require_workflow_run_member), db: AsyncSession = Depends(get_db),
):
    run, _caller = run_ctx
    blocks = await list_human_blocks(db, run.id)
    await db.commit()
    return blocks


@router.get("/workflows/runs/{run_id}/human-blocks/{block_id}", response_model=WorkflowHumanInputResponse)
async def get_human_block_endpoint(
    block_id: uuid.UUID,
    run_ctx: tuple[WorkflowRun, OrganizationMember] = Depends(require_workflow_run_member), db: AsyncSession = Depends(get_db),
):
    run, _caller = run_ctx
    block = await get_human_approval(db, block_id)
    if block is None or block.workflow_run_id != run.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return block


@router.post("/workflows/runs/{run_id}/human-blocks/{block_id}/submit", response_model=WorkflowHumanInputResponse)
async def submit_human_block_endpoint(
    block_id: uuid.UUID, payload: WorkflowHumanInputSubmitRequest,
    run_ctx: tuple[WorkflowRun, OrganizationMember] = Depends(require_workflow_run_member), db: AsyncSession = Depends(get_db),
):
    run, caller = run_ctx
    existing = await get_human_approval(db, block_id)
    if existing is None or existing.workflow_run_id != run.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        updated = await submit_human_input(db, block_id, caller.user_id, payload.value)
    except WorkflowBlockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This human input is no longer pending")
    await db.commit()
    schedule_workflow_resume(run.id, updated.id)
    return updated


# ------------------------------------- Partie 5.4.13 -- workflow versioning -------------------------------------


@router.get("/workflows/{workflow_id}/versions", response_model=list[WorkflowVersionResponse])
async def list_workflow_versions_endpoint(
    workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_member), db: AsyncSession = Depends(get_db),
):
    workflow, _caller = workflow_ctx
    return await list_workflow_versions(db, workflow.id)


@router.get("/workflows/{workflow_id}/versions/{version_number}", response_model=WorkflowVersionResponse)
async def get_workflow_version_endpoint(
    version_number: int,
    workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_member), db: AsyncSession = Depends(get_db),
):
    workflow, _caller = workflow_ctx
    version = await get_workflow_version(db, workflow.id, version_number)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return version


@router.post("/workflows/{workflow_id}/versions/create", response_model=WorkflowVersionResponse)
async def create_workflow_version_endpoint(
    payload: WorkflowVersionCreateRequest,
    workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_manager), db: AsyncSession = Depends(get_db),
):
    workflow, caller = workflow_ctx
    version = await create_workflow_version(db, workflow.id, caller.user_id, payload.comment)
    await db.commit()
    return version


@router.post("/workflows/{workflow_id}/versions/restore", response_model=WorkflowResponse)
async def restore_workflow_version_endpoint(
    payload: WorkflowVersionRestoreRequest,
    workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_manager), db: AsyncSession = Depends(get_db),
):
    workflow, caller = workflow_ctx
    try:
        restored = await restore_workflow_version(db, workflow.id, payload.version_number, caller.user_id)
    except WorkflowVersionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(restored)
    return restored


@router.post("/workflows/{workflow_id}/versions/diff", response_model=WorkflowVersionDiffResponse)
async def diff_workflow_versions_endpoint(
    payload: WorkflowVersionDiffRequest,
    workflow_ctx: tuple[Workflow, OrganizationMember] = Depends(require_workflow_member), db: AsyncSession = Depends(get_db),
):
    workflow, _caller = workflow_ctx
    try:
        return await diff_workflow_versions(db, workflow.id, payload.version_a, payload.version_b)
    except WorkflowVersionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
