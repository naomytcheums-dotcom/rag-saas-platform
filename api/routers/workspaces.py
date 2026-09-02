"""
Etape 1.2.4 -- workspace CRUD. Create/rename/delete are gated by
require_org_manager / require_workspace_manager (Owner, Admin, or
Manager) -- the Manager role's second capability, alongside member
invitation (api/routers/organization_members.py). Listing is gated by
the weaker require_org_member instead: a Member or Viewer has no reason
to be hidden from what workspaces exist in their own organization (they
just can't create, rename, or delete one) -- the spec named permissions
for the CRUD-mutating verbs only, this is the one judgment call filled
in rather than left unstated.

Etape 1.2.8: update/delete now use require_workspace_permission(action)
instead of require_workspace_manager directly -- a Viewer or Member
holding a specific, granted, non-expired resource_permissions row for
THIS workspace passes immediately; absence of one falls through to the
exact same Owner/Admin/Manager check as before. Purely additive -- every
existing test in tests/test_workspaces.py (none of which ever grant a
resource_permissions row) exercises the unchanged fallback path.
create_workspace stays on require_org_manager: a workspace has no id to
grant a permission against before it exists.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.audit_log import AuditAction
from api.models.organization import OrganizationMember
from api.models.workspace import Workspace
from api.schemas.workspaces import WorkspaceCreateRequest, WorkspaceEntry, WorkspaceListResponse, WorkspaceUpdateRequest
from api.security.audit_log import log_audit_action
from api.security.organizations import require_org_manager, require_org_member
from api.security.workspaces import require_workspace_permission
from api.utils import client_ip

router = APIRouter(tags=["workspaces"])
logger = logging.getLogger(__name__)


def _to_entry(workspace: Workspace) -> WorkspaceEntry:
    return WorkspaceEntry(
        id=workspace.id, organization_id=workspace.organization_id, name=workspace.name,
        created_by=workspace.created_by, created_at=workspace.created_at, updated_at=workspace.updated_at,
    )


@router.get("/organizations/{org_id}/workspaces", response_model=WorkspaceListResponse)
async def list_workspaces(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Workspace).where(Workspace.organization_id == org_id).order_by(Workspace.created_at.asc())
    )).scalars().all()
    return WorkspaceListResponse(items=[_to_entry(w) for w in rows])


@router.post("/organizations/{org_id}/workspaces", response_model=WorkspaceEntry, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    org_id: uuid.UUID, payload: WorkspaceCreateRequest, request: Request,
    caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    workspace = Workspace(organization_id=org_id, name=payload.name, created_by=caller.user_id)
    db.add(workspace)
    await db.flush()

    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.WORKSPACE_CREATED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={"organization_id": str(org_id), "workspace_id": str(workspace.id), "name": payload.name},
    )
    await db.commit()
    await db.refresh(workspace)
    return _to_entry(workspace)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceEntry)
async def update_workspace(
    payload: WorkspaceUpdateRequest,
    caller_ctx: tuple[Workspace, OrganizationMember] = Depends(require_workspace_permission("update")),
    db: AsyncSession = Depends(get_db),
):
    workspace, _caller = caller_ctx
    workspace.name = payload.name
    await db.commit()
    # updated_at has onupdate=func.now() -- see api/routers/organizations.py's
    # update_organization for why an explicit refresh is required here
    # (an implicit sync-style reload would raise MissingGreenlet under
    # this async session).
    await db.refresh(workspace)
    return _to_entry(workspace)


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(
    request: Request,
    caller_ctx: tuple[Workspace, OrganizationMember] = Depends(require_workspace_permission("delete")),
    db: AsyncSession = Depends(get_db),
):
    workspace, caller = caller_ctx

    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.WORKSPACE_DELETED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={"organization_id": str(workspace.organization_id), "workspace_id": str(workspace.id)},
    )
    await db.execute(delete(Workspace).where(Workspace.id == workspace.id))
    await db.commit()
    return {"message": "Workspace deleted"}
