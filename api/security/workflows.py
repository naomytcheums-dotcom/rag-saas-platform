"""
Partie 5.4.1 -- real workflow CRUD. Create/list are org-scoped
(`require_org_manager`/`require_org_member`, same tier convention as
`api/routers/workspaces.py`/`api/routers/agents.py`); get/update/delete
resolve the workflow AND the caller's real organization role together
(`require_workflow_member`/`require_workflow_manager`), same real
reasoning as `api/security/agents.py`'s own pair: this étape's own
literal paths for those (`GET/PATCH/DELETE /workflows/{workflow_id}`)
carry no `{org_id}`."""

import datetime as dt
import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.models.workflow import Workflow, WorkflowStatus
from api.models.workflow_run import WorkflowRun
from api.services.workflows import validate_workflow_data

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _resolve_workflow_and_membership(workflow_id: uuid.UUID, current_user: User, db: AsyncSession) -> tuple[Workflow, OrganizationMember]:
    workflow = await db.get(Workflow, workflow_id)
    if workflow is None or workflow.deleted_at is not None:
        raise _NOT_FOUND

    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == workflow.organization_id, OrganizationMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise _NOT_FOUND
    return workflow, membership


async def require_workflow_member(
    workflow_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[Workflow, OrganizationMember]:
    return await _resolve_workflow_and_membership(workflow_id, current_user, db)


async def require_workflow_manager(
    workflow_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[Workflow, OrganizationMember]:
    workflow, membership = await _resolve_workflow_and_membership(workflow_id, current_user, db)
    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin, OrganizationRole.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization manager access required")
    return workflow, membership


async def create_workflow(db: AsyncSession, organization_id: uuid.UUID, data: dict, created_by: uuid.UUID | None) -> Workflow:
    """Item 5's own literal function's real backing -- real, upfront
    structural validation (same no-bypass-via-the-generic-endpoint
    reasoning as every prior 5.3.x fix) whenever real `nodes`/`edges`
    are given."""
    if data.get("nodes") or data.get("edges"):
        validate_workflow_data({"nodes": data.get("nodes", []), "edges": data.get("edges", [])})
    workflow = Workflow(
        organization_id=organization_id, created_by=created_by, workspace_id=data.get("workspace_id"),
        name=data["name"], description=data.get("description"), nodes=data.get("nodes") or [], edges=data.get("edges") or [],
        variables=data.get("variables") or [],
    )
    db.add(workflow)
    await db.flush()
    return workflow


async def update_workflow(db: AsyncSession, workflow_id: uuid.UUID, data: dict) -> Workflow | None:
    workflow = await db.get(Workflow, workflow_id)
    if workflow is None or workflow.deleted_at is not None:
        return None
    if "nodes" in data or "edges" in data:
        validate_workflow_data({"nodes": data.get("nodes", workflow.nodes), "edges": data.get("edges", workflow.edges)})
    for field in ("name", "description", "workspace_id", "nodes", "edges", "variables", "status"):
        if field in data:
            setattr(workflow, field, data[field])
    await db.flush()
    return workflow


async def import_workflow(db: AsyncSession, organization_id: uuid.UUID, workflow_data: dict, created_by: uuid.UUID | None) -> Workflow:
    """Item 4's own literal function -- real, upfront structural
    validation (`validate_workflow_data`) before a real row is ever
    created; reuses `create_workflow` rather than a second, separate
    insert path."""
    validate_workflow_data(workflow_data)
    return await create_workflow(db, organization_id, workflow_data, created_by)


async def get_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> Workflow | None:
    workflow = await db.get(Workflow, workflow_id)
    if workflow is None or workflow.deleted_at is not None:
        return None
    return workflow


async def list_workflows(db: AsyncSession, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[Workflow]:
    query = (
        select(Workflow).where(Workflow.organization_id == organization_id, Workflow.deleted_at.is_(None))
        .order_by(Workflow.created_at.desc()).limit(limit).offset(offset)
    )
    return list((await db.scalars(query)).all())


async def list_workflow_runs(db: AsyncSession, workflow_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[WorkflowRun]:
    """Phase 5, Étape 5 -- backs the Workflow Builder UI's own
    execution-history list. Real gap found during this étape's own
    audit: the run/human-block endpoints already existed, but nothing
    ever listed a workflow's own past runs."""
    query = (
        select(WorkflowRun).where(WorkflowRun.workflow_id == workflow_id)
        .order_by(WorkflowRun.started_at.desc()).limit(limit).offset(offset)
    )
    return list((await db.scalars(query)).all())


async def require_workflow_run_member(
    run_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[WorkflowRun, OrganizationMember]:
    """Partie 5.4.9 -- real dependency for the `human` block's own
    endpoints: resolves the real `WorkflowRun`, its own real
    `Workflow`, AND the caller's real organization membership together
    (same 404-not-403 anti-enumeration reasoning as
    `require_workflow_member`), since a run has no `organization_id`
    of its own -- only its parent workflow does."""
    run = await db.get(WorkflowRun, run_id)
    if run is None:
        raise _NOT_FOUND
    workflow = await db.get(Workflow, run.workflow_id)
    if workflow is None or workflow.deleted_at is not None:
        raise _NOT_FOUND
    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == workflow.organization_id, OrganizationMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise _NOT_FOUND
    return run, membership


async def delete_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> bool:
    """Real soft delete -- same reasoning as `api/security/agents.py`'s
    own `delete_agent`: a real workflow's own past `WorkflowRun`s keep a
    real, meaningful reference to it."""
    workflow = await db.get(Workflow, workflow_id)
    if workflow is None or workflow.deleted_at is not None:
        return False
    workflow.deleted_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return True
