"""
Etape 1.2.1 -- Super Admin. The first genuinely superadmin-exclusive
capability this codebase has: changing another account's role. Until
now, a role change was only ever possible via direct database access
(every test file's own `_promote_to_admin`-style helper) -- this is the
first real API surface for it, gated by require_superadmin
(api/dependencies.py) rather than the more permissive require_admin
every other /admin/* route uses: granting or revoking admin/superadmin
access is a more consequential action than reading audit logs or
configuring an SSO connection.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_superadmin
from api.models.audit_log import AuditAction
from api.models.user import User, UserRole
from api.schemas.admin_users import UserRoleUpdateRequest, UserRoleUpdateResponse
from api.security.audit_log import log_audit_action

router = APIRouter(tags=["admin"])


@router.patch("/admin/users/{user_id}/role", response_model=UserRoleUpdateResponse)
async def update_user_role(
    user_id: uuid.UUID, payload: UserRoleUpdateRequest,
    superadmin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db),
):
    """
    Scoped by user_id, 404 for an unknown target -- same shape as every
    other /admin/{id} lookup in this codebase.

    Safety net: refuses to demote the LAST remaining superadmin. Without
    it, a lone superadmin could accidentally lock the account tier out
    of existence entirely -- no one left able to reach this very
    endpoint to undo the mistake. Demoting yourself is otherwise allowed
    as long as at least one other superadmin remains.
    """
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if target.role == UserRole.superadmin and payload.role != UserRole.superadmin:
        other_superadmins_remain = await db.scalar(
            select(func.count()).select_from(User).where(User.role == UserRole.superadmin, User.id != target.id)
        )
        if not other_superadmins_remain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the last remaining superadmin",
            )

    previous_role = target.role
    target.role = payload.role
    await log_audit_action(
        db, user_id=superadmin.id, action=AuditAction.USER_ROLE_CHANGED, ip=None, user_agent=None,
        success=True, metadata={"target_user_id": str(target.id), "previous_role": previous_role.value, "new_role": payload.role.value},
    )
    await db.commit()
    return UserRoleUpdateResponse(user_id=target.id, role=target.role)
