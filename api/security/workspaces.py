"""
Etape 1.2.4 -- permission checking for the two workspace endpoints that
address a workspace directly by its own id (PATCH/DELETE /workspaces/{id})
rather than being nested under /organizations/{org_id}/... . Those two
have no org_id path parameter for require_org_manager
(api/security/organizations.py) to resolve automatically, so this module
looks the organization up FROM the workspace first.
"""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_current_user
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.models.workspace import Workspace


async def require_workspace_manager(
    workspace_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[Workspace, OrganizationMember]:
    """
    Returns (workspace, caller's own membership) -- callers need both:
    the workspace to act on, and the membership for audit-logging who
    acted. 404, not 403, for a non-member -- same anti-enumeration
    reasoning as api/security/organizations.py's require_org_member: a
    workspace's mere existence (and which organization it belongs to)
    isn't information a non-member should learn from a permission error
    alone, collapsed with "no such workspace" into one response.
    """
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    workspace = await db.get(Workspace, workspace_id)
    if workspace is None:
        raise not_found

    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == workspace.organization_id, OrganizationMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise not_found

    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin, OrganizationRole.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization manager access required")

    return workspace, membership
