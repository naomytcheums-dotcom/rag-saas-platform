"""Partie 11.2 -- platform-admin organization management. Every
mutating action is audited via the existing real audit log."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db, require_admin, require_superadmin
from api.models.audit_log import AuditAction
from api.models.user import User
from api.schemas.admin_dashboard import (
    OrganizationAdminListResponse,
    OrganizationAdminResponse,
    OrganizationMemberAdminResponse,
    OrganizationSuspendRequest,
    OrganizationUpdateAdminRequest,
)
from api.security.audit_log import log_audit_action
from api.services.admin_organizations import (
    OrganizationNotFoundError,
    activate_organization,
    delete_organization_admin,
    get_organization_admin,
    get_organization_members_admin,
    get_organization_usage_admin,
    list_organizations_admin,
    suspend_organization,
    update_organization_admin,
)
from api.utils import MAX_PAGE_SIZE, client_ip

router = APIRouter(prefix="/admin/organizations", tags=["Admin Organizations"])


@router.get("", response_model=OrganizationAdminListResponse)
async def list_organizations_endpoint(limit: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0), suspended: bool | None = None, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows, total = await list_organizations_admin(db, limit=limit, offset=offset, suspended=suspended)
    return OrganizationAdminListResponse(items=[OrganizationAdminResponse.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/{org_id}", response_model=OrganizationAdminResponse)
async def get_organization_endpoint(org_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        org = await get_organization_admin(db, org_id)
    except OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return OrganizationAdminResponse.model_validate(org)


@router.patch("/{org_id}", response_model=OrganizationAdminResponse)
async def update_organization_endpoint(org_id: uuid.UUID, payload: OrganizationUpdateAdminRequest, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        org = await update_organization_admin(db, org_id, name=payload.name)
    except OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return OrganizationAdminResponse.model_validate(org)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization_endpoint(org_id: uuid.UUID, request: Request, admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    try:
        await delete_organization_admin(db, org_id)
    except OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await log_audit_action(
        db, user_id=admin.id, action=AuditAction.ORGANIZATION_DELETED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=org_id, resource_type="organization", resource_id=str(org_id),
    )
    await db.commit()


@router.post("/{org_id}/suspend", response_model=OrganizationAdminResponse)
async def suspend_organization_endpoint(org_id: uuid.UUID, payload: OrganizationSuspendRequest, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        org = await suspend_organization(db, org_id, reason=payload.reason)
    except OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await log_audit_action(
        db, user_id=admin.id, action=AuditAction.ORGANIZATION_SUSPENDED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=org_id, resource_type="organization", resource_id=str(org_id), metadata={"reason": payload.reason},
    )
    await db.commit()
    return OrganizationAdminResponse.model_validate(org)


@router.post("/{org_id}/activate", response_model=OrganizationAdminResponse)
async def activate_organization_endpoint(org_id: uuid.UUID, request: Request, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        org = await activate_organization(db, org_id)
    except OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await log_audit_action(
        db, user_id=admin.id, action=AuditAction.ORGANIZATION_ACTIVATED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=org_id, resource_type="organization", resource_id=str(org_id),
    )
    await db.commit()
    return OrganizationAdminResponse.model_validate(org)


@router.get("/{org_id}/members", response_model=list[OrganizationMemberAdminResponse])
async def get_organization_members_endpoint(org_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    members = await get_organization_members_admin(db, org_id)
    return [OrganizationMemberAdminResponse(user_id=m.user_id, email=m.user.email, role=m.role.value, joined_at=m.joined_at) for m in members]


@router.get("/{org_id}/usage")
async def get_organization_usage_endpoint(org_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await get_organization_usage_admin(db, org_id)


@router.get("/{org_id}/billing")
async def get_organization_billing_endpoint(org_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from api.services.admin_subscriptions import get_or_create_subscription

    sub = await get_or_create_subscription(db, org_id)
    await db.commit()
    return {"subscription_id": str(sub.id), "plan_id": str(sub.plan_id), "status": sub.status.value}


@router.get("/{org_id}/activity")
async def get_organization_activity_endpoint(org_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE), _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from api.routers.audit import _list_audit_logs

    return await _list_audit_logs(db, user_id=None, action=None, since=None, until=None, limit=limit, offset=0, organization_id=org_id)
