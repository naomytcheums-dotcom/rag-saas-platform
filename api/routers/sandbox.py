"""Sandbox Environment — isolated dev/test data CRUD."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.models.sandbox import SandboxEnvironment
from api.security.permissions import require_permission
from api.security.organizations import require_org_admin, require_org_member

router = APIRouter(tags=["sandbox"])


@router.get("/organizations/{org_id}/sandbox")
async def list_sandboxes(
    org_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("settings:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SandboxEnvironment).where(SandboxEnvironment.organization_id == org_id))
    return result.scalars().all()


@router.post("/organizations/{org_id}/sandbox", status_code=status.HTTP_201_CREATED)
async def create_sandbox(
    org_id: uuid.UUID,
    name: str,
    data_ttl_hours: int = 24,
    _caller: OrganizationMember = Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
):
    sandbox = SandboxEnvironment(
        organization_id=org_id,
        name=name,
        data_ttl_hours=data_ttl_hours,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=data_ttl_hours),
    )
    db.add(sandbox)
    await db.commit()
    await db.refresh(sandbox)
    return sandbox


@router.delete("/organizations/{org_id}/sandbox/{sandbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sandbox(
    org_id: uuid.UUID,
    sandbox_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
):
    sandbox = await db.get(SandboxEnvironment, sandbox_id)
    if not sandbox or sandbox.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(sandbox)
    await db.commit()


@router.post("/organizations/{org_id}/sandbox/{sandbox_id}/reset")
async def reset_sandbox(
    org_id: uuid.UUID,
    sandbox_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
):
    sandbox = await db.get(SandboxEnvironment, sandbox_id)
    if not sandbox or sandbox.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Not found")
    sandbox.expires_at = datetime.now(timezone.utc) + timedelta(hours=sandbox.data_ttl_hours)
    await db.commit()
    return {"status": "reset", "expires_at": sandbox.expires_at}
