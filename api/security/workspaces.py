"""
Etape 1.2.4 -- permission checking for the two workspace endpoints that
address a workspace directly by its own id (PATCH/DELETE /workspaces/{id})
rather than being nested under /organizations/{org_id}/... . Those two
have no org_id path parameter for require_org_manager
(api/security/organizations.py) to resolve automatically, so this module
looks the organization up FROM the workspace first.

Etape 1.2.8: replaced the original require_workspace_manager with
require_workspace_permission(action) -- a granular-permission check IN
FRONT of the exact same role check require_workspace_manager used to do
on its own. A matching, non-expired resource_permissions row grants
access immediately; its absence falls through to the unchanged
Owner/Admin/Manager check. See api/security/resource_permissions.py's
module docstring for the full priority-order reasoning. The old
require_workspace_manager was removed rather than kept alongside this --
it had zero remaining call sites once both PATCH and DELETE moved to
require_workspace_permission, and keeping it would have meant two
copies of the same role check to keep in sync by hand.
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
from api.security.resource_permissions import check_resource_permission


async def _resolve_workspace_and_membership(
    workspace_id: uuid.UUID, current_user: User, db: AsyncSession,
) -> tuple[Workspace, OrganizationMember]:
    """404, not 403, for a non-member -- same anti-enumeration reasoning
    as api/security/organizations.py's require_org_member: a workspace's
    mere existence (and which organization it belongs to) isn't
    information a non-member should learn from a permission error alone,
    collapsed with "no such workspace" into one response."""
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

    return workspace, membership


def require_workspace_permission(action: str):
    """
    Used by PATCH/DELETE /workspaces/{id} (api/routers/workspaces.py),
    each naming its own action ("update"/"delete") for the granular
    check. Returns (workspace, caller's own membership) -- callers need
    both: the workspace to act on, and the membership for
    audit-logging who acted.
    """

    async def _check(
        workspace_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
    ) -> tuple[Workspace, OrganizationMember]:
        workspace, membership = await _resolve_workspace_and_membership(workspace_id, current_user, db)

        if await check_resource_permission(
            db, user_id=current_user.id, resource_type="workspace", resource_id=workspace_id, action=action,
        ):
            return workspace, membership

        if membership.role not in (OrganizationRole.owner, OrganizationRole.admin, OrganizationRole.manager):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization manager access required")

        return workspace, membership

    return _check
