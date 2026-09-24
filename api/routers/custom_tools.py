"""
Partie 5.2.10 -- real custom-tool management + execution. Create/list
are org-scoped (`require_org_manager`/`require_org_member`); get/
update/delete/execute resolve the tool AND the caller's real
organization role together (`require_custom_tool_member`/
`require_custom_tool_manager`), same reasoning as
`api/routers/agents.py`.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.custom_tool import CustomTool
from api.models.organization import OrganizationMember
from api.schemas.custom_tools import (
    CustomToolCreateRequest, CustomToolExecuteRequest, CustomToolExecuteResponse, CustomToolResponse,
    CustomToolUpdateRequest,
)
from api.security.permissions import require_permission
from api.security.custom_tools import (
    CustomToolError, create_custom_tool, delete_custom_tool, get_custom_tools, require_custom_tool_manager,
    require_custom_tool_member, update_custom_tool,
)
from api.security.organizations import require_org_manager, require_org_member
from api.services.custom_tools import execute_custom_tool

router = APIRouter(tags=["custom-tools"])


@router.post("/organizations/{org_id}/custom-tools", response_model=CustomToolResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_tool_endpoint(
    org_id: uuid.UUID, payload: CustomToolCreateRequest,
    caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    try:
        tool = await create_custom_tool(db, org_id, payload.model_dump(by_alias=True), caller.user_id)
    except CustomToolError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(tool)
    return tool


@router.get("/organizations/{org_id}/custom-tools", response_model=list[CustomToolResponse])
async def list_custom_tools_endpoint(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("integrations:read")), db: AsyncSession = Depends(get_db),
):
    return await get_custom_tools(db, org_id)


@router.get("/custom-tools/{tool_id}", response_model=CustomToolResponse)
async def get_custom_tool_endpoint(tool_ctx: tuple[CustomTool, OrganizationMember] = Depends(require_custom_tool_member)):
    tool, _caller = tool_ctx
    return tool


@router.patch("/custom-tools/{tool_id}", response_model=CustomToolResponse)
async def update_custom_tool_endpoint(
    payload: CustomToolUpdateRequest,
    tool_ctx: tuple[CustomTool, OrganizationMember] = Depends(require_custom_tool_manager), db: AsyncSession = Depends(get_db),
):
    tool, _caller = tool_ctx
    try:
        updated = await update_custom_tool(db, tool.id, payload.model_dump(by_alias=True, exclude_unset=True))
    except CustomToolError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(updated)
    return updated


@router.delete("/custom-tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_tool_endpoint(
    tool_ctx: tuple[CustomTool, OrganizationMember] = Depends(require_custom_tool_manager), db: AsyncSession = Depends(get_db),
):
    tool, _caller = tool_ctx
    await delete_custom_tool(db, tool.id)
    await db.commit()


@router.post("/custom-tools/{tool_id}/execute", response_model=CustomToolExecuteResponse)
async def execute_custom_tool_endpoint(
    payload: CustomToolExecuteRequest,
    tool_ctx: tuple[CustomTool, OrganizationMember] = Depends(require_custom_tool_member), db: AsyncSession = Depends(get_db),
):
    tool, _caller = tool_ctx
    try:
        result = await execute_custom_tool(db, tool.id, payload.params)
    except CustomToolError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result
