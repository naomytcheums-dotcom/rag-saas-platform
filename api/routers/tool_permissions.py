"""
Partie 5.1.3 -- granting/revoking/listing per-agent/per-user tool
permissions.

**A real, documented deviation from this étape's own literal paths**
(`POST /agents/{agent_id}/tools/{tool_name}/permissions`, no
organization in the path): every real permission grant here needs a
real tenant boundary (see api/models/tool_permission.py's own
docstring) -- so every route below is mounted under
`/organizations/{org_id}/...`, `require_org_admin`-gated, matching
`api/routers/quotas.py`'s own established convention rather than
introducing an unscoped surface with no defined authority.

`GET /users/me/tools/permissions` keeps its own literal, org-scoped
shape too (`/organizations/{org_id}/users/me/tools/permissions`) --
any real member can read their OWN permissions (require_org_member),
not just an Admin.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.tool_permissions import AvailableToolResponse, ToolPermissionGrantRequest, ToolPermissionResponse
from api.security.organizations import require_org_admin, require_org_member
from api.security.tool_permissions import (
    get_available_tools, get_tool_permissions, grant_tool_permission, revoke_tool_permission,
)

router = APIRouter(tags=["tool-permissions"])


@router.post("/organizations/{org_id}/agents/{agent_id}/tools/{tool_name}/permissions", response_model=ToolPermissionResponse)
async def grant_agent_tool_permission(
    org_id: uuid.UUID, agent_id: str, tool_name: str, payload: ToolPermissionGrantRequest,
    caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    row = await grant_tool_permission(
        db, org_id, agent_id, payload.user_id, tool_name, payload.permission, granted_by=caller.user_id,
    )
    await db.commit()
    return row


@router.delete("/organizations/{org_id}/agents/{agent_id}/tools/{tool_name}/permissions/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_agent_tool_permission(
    org_id: uuid.UUID, agent_id: str, tool_name: str, user_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    revoked = await revoke_tool_permission(db, org_id, agent_id, user_id, tool_name)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching permission grant")
    await db.commit()


@router.get("/organizations/{org_id}/agents/{agent_id}/tools/permissions", response_model=list[ToolPermissionResponse])
async def list_agent_tool_permissions(
    org_id: uuid.UUID, agent_id: str,
    _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    return await get_tool_permissions(db, org_id, agent_id=agent_id)


@router.get("/organizations/{org_id}/users/me/tools/permissions", response_model=list[AvailableToolResponse])
async def get_my_available_tools(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    tools = await get_available_tools(db, org_id, agent_id=None, user_id=current_user.id)
    return [AvailableToolResponse(name=t.name, description=t.description, parameters=t.parameters) for t in tools]
