"""Partie 11.3 -- platform-admin user management. Kept in its own
router file, separate from api/routers/admin_users.py (which stays as
the real, existing superadmin-only role-change endpoint) -- these are
Admin+ (not superadmin-only) CRUD/lifecycle actions on other accounts."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_admin
from api.models.audit_log import AuditAction
from api.models.user import User
from api.schemas.admin_dashboard import (
    UserAdminListResponse,
    UserAdminResponse,
    UserSessionAdminResponse,
    UserSuspendRequest,
    UserUpdateAdminRequest,
)
from api.security.audit_log import log_audit_action
from api.services.admin_users_management import (
    UserNotFoundError,
    activate_user,
    get_user_admin,
    get_user_sessions_admin,
    list_users_admin,
    suspend_user,
    terminate_user_session_admin,
    update_user_admin,
    verify_user_email_admin,
)
from api.utils import client_ip

router = APIRouter(prefix="/admin/users", tags=["Admin Users"])


@router.get("", response_model=UserAdminListResponse)
async def list_users_endpoint(limit: int = Query(default=20, ge=1, le=200), offset: int = Query(default=0, ge=0), search: str | None = None, is_active: bool | None = None, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows, total = await list_users_admin(db, limit=limit, offset=offset, search=search, is_active=is_active)
    return UserAdminListResponse(items=[UserAdminResponse.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/{user_id}", response_model=UserAdminResponse)
async def get_user_endpoint(user_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        user = await get_user_admin(db, user_id)
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return UserAdminResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserAdminResponse)
async def update_user_endpoint(user_id: uuid.UUID, payload: UserUpdateAdminRequest, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        user = await update_user_admin(db, user_id, full_name=payload.full_name, company=payload.company)
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return UserAdminResponse.model_validate(user)


@router.post("/{user_id}/suspend", response_model=UserAdminResponse)
async def suspend_user_endpoint(user_id: uuid.UUID, payload: UserSuspendRequest, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        user = await suspend_user(db, user_id, reason=payload.reason)
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await log_audit_action(
        db, user_id=admin.id, action=AuditAction.USER_SUSPENDED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, resource_type="user", resource_id=str(user_id), metadata={"reason": payload.reason},
    )
    await db.commit()
    return UserAdminResponse.model_validate(user)


@router.post("/{user_id}/activate", response_model=UserAdminResponse)
async def activate_user_endpoint(user_id: uuid.UUID, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        user = await activate_user(db, user_id)
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await log_audit_action(
        db, user_id=admin.id, action=AuditAction.USER_ACTIVATED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, resource_type="user", resource_id=str(user_id),
    )
    await db.commit()
    return UserAdminResponse.model_validate(user)


@router.post("/{user_id}/reset-password")
async def reset_user_password_endpoint(user_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Real: triggers the same real password-reset EMAIL flow a user's
    own "forgot password" link uses (create_and_send_password_reset) --
    an admin never sees or sets the new password directly."""
    try:
        user = await get_user_admin(db, user_id)
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    from api.services.password_reset import create_and_send_password_reset

    await create_and_send_password_reset(db, user)
    await db.commit()
    return {"sent": True}


@router.post("/{user_id}/verify-email", response_model=UserAdminResponse)
async def verify_user_email_endpoint(user_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        user = await verify_user_email_admin(db, user_id)
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return UserAdminResponse.model_validate(user)


@router.get("/{user_id}/sessions", response_model=list[UserSessionAdminResponse])
async def get_user_sessions_endpoint(user_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    sessions = await get_user_sessions_admin(db, user_id)
    return [UserSessionAdminResponse.model_validate(s) for s in sessions]


@router.delete("/{user_id}/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def terminate_user_session_endpoint(user_id: uuid.UUID, session_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    terminated = await terminate_user_session_admin(db, user_id, session_id)
    if not terminated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()


@router.get("/{user_id}/activity")
async def get_user_activity_endpoint(user_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=200), _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Real, deliberate: two DIFFERENT real things could be meant by "a
    user's activity" -- actions that USER performed (AuditLog.user_id),
    or admin actions performed ON them (resource_type="user",
    resource_id=user_id, e.g. a platform admin suspending them). Both
    are real and useful; this returns the union so an admin reviewing
    an account sees the complete real picture."""
    from sqlalchemy import func, or_, select

    from api.models.audit_log import AuditLog
    from api.routers.audit import _to_entry
    from api.schemas.audit import AuditLogListResponse

    filters = or_(AuditLog.user_id == user_id, (AuditLog.resource_type == "user") & (AuditLog.resource_id == str(user_id)))
    total = await db.scalar(select(func.count()).select_from(AuditLog).where(filters)) or 0
    rows = (await db.scalars(select(AuditLog).where(filters).order_by(AuditLog.timestamp.desc()).limit(limit))).all()
    return AuditLogListResponse(items=[_to_entry(r) for r in rows], total=total, limit=limit, offset=0)
