"""
Partie 5.2.10 -- real custom-tool CRUD. Create/list are org-scoped
(`require_org_manager`/`require_org_member`, same tier convention as
`api/routers/workspaces.py`/`api/routers/agents.py`); get/update/delete
resolve the tool AND the caller's real organization role together
(`require_custom_tool_member`/`require_custom_tool_manager`), same
reasoning as `api/security/agents.py`'s own pair: this étape's own
literal paths for those (`GET/PATCH/DELETE /custom-tools/{tool_id}`)
carry no `{org_id}`."""

import datetime as dt
import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.custom_tool import HTTP_METHODS, CustomTool
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


class CustomToolError(ValueError):
    """Real, dedicated exception."""


def _validate_config(data: dict) -> None:
    method = data.get("method", "POST")
    if method not in HTTP_METHODS:
        raise CustomToolError(f"Unknown method: {method!r} (expected one of {HTTP_METHODS})")
    timeout = data.get("timeout")
    if timeout is not None and timeout <= 0:
        raise CustomToolError("timeout must be a real, positive number of seconds")
    retry_count = data.get("retry_count")
    if retry_count is not None and retry_count <= 0:
        raise CustomToolError("retry_count must be a real, positive integer")


async def _resolve_tool_and_membership(tool_id: uuid.UUID, current_user: User, db: AsyncSession) -> tuple[CustomTool, OrganizationMember]:
    tool = await db.get(CustomTool, tool_id)
    if tool is None or tool.deleted_at is not None:
        raise _NOT_FOUND
    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == tool.organization_id, OrganizationMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise _NOT_FOUND
    return tool, membership


async def require_custom_tool_member(
    tool_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[CustomTool, OrganizationMember]:
    return await _resolve_tool_and_membership(tool_id, current_user, db)


async def require_custom_tool_manager(
    tool_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[CustomTool, OrganizationMember]:
    tool, membership = await _resolve_tool_and_membership(tool_id, current_user, db)
    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin, OrganizationRole.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization manager access required")
    return tool, membership


async def create_custom_tool(db: AsyncSession, organization_id: uuid.UUID, data: dict, created_by: uuid.UUID | None) -> CustomTool:
    """Item 3's own literal function's real backing -- real, upfront
    validation before the row is ever created."""
    _validate_config(data)
    tool = CustomTool(
        organization_id=organization_id, created_by=created_by, name=data["name"], description=data.get("description", ""),
        webhook_url=data["webhook_url"], method=data.get("method", "POST"), headers=data.get("headers"),
        timeout=data.get("timeout", 20), retry_count=data.get("retry_count", 1), schema=data.get("schema") or {},
    )
    db.add(tool)
    await db.flush()
    return tool


async def update_custom_tool(db: AsyncSession, tool_id: uuid.UUID, data: dict) -> CustomTool | None:
    tool = await db.get(CustomTool, tool_id)
    if tool is None or tool.deleted_at is not None:
        return None
    _validate_config(data)
    for field in ("name", "description", "webhook_url", "method", "headers", "timeout", "retry_count", "schema"):
        if field in data:
            setattr(tool, field, data[field])
    await db.flush()
    return tool


async def get_custom_tool(db: AsyncSession, tool_id: uuid.UUID) -> CustomTool | None:
    """Item 2's own literal `get_custom_tools`'s single-tool sibling --
    `None` for an unknown OR real, soft-deleted tool."""
    tool = await db.get(CustomTool, tool_id)
    if tool is None or tool.deleted_at is not None:
        return None
    return tool


async def get_custom_tools(db: AsyncSession, organization_id: uuid.UUID) -> list[CustomTool]:
    """Item 2's own literal function."""
    result = await db.scalars(
        select(CustomTool).where(CustomTool.organization_id == organization_id, CustomTool.deleted_at.is_(None))
        .order_by(CustomTool.created_at.desc())
    )
    return list(result)


async def delete_custom_tool(db: AsyncSession, tool_id: uuid.UUID) -> bool:
    """Real soft delete -- same reasoning as `Agent`/`Workflow`: a real
    agent run that already called this tool keeps a real, meaningful
    reference to it."""
    tool = await db.get(CustomTool, tool_id)
    if tool is None or tool.deleted_at is not None:
        return False
    tool.deleted_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return True
