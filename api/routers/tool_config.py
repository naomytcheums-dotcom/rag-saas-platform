"""
Partie 5.1.4 (tool timeout) + 5.1.5 (per-tool budget) -- real,
platform-wide admin endpoints. Mounted under `/admin/tools/...`,
`require_superadmin`-gated -- see api/models/tool_config.py's own
module docstring for why (no per-organization scope makes sense for a
config that tunes shared infrastructure, and `require_superadmin` is
this codebase's only real precedent for an unscoped admin surface).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_superadmin
from api.models.tool_config import ToolBudget
from api.models.user import User
from api.schemas.tool_config import (
    ToolBudgetResponse, ToolBudgetUpdateRequest, ToolFallbackCreateRequest, ToolFallbackResponse,
    ToolTimeoutResponse, ToolTimeoutUpdateRequest,
)
from api.services.fallback import delete_tool_fallbacks, list_tool_fallbacks, set_tool_fallback
from api.services.tool_budget import list_tool_budgets, reset_tool_budget, set_tool_budget
from api.services.tool_timeout import list_tool_timeouts, set_tool_timeout

router = APIRouter(prefix="/admin/tools", tags=["tool-config"])


@router.get("/timeout", response_model=list[ToolTimeoutResponse])
async def get_tool_timeouts(_admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    return await list_tool_timeouts(db)


@router.patch("/{tool_name}/timeout", response_model=ToolTimeoutResponse)
async def update_tool_timeout(
    tool_name: str, payload: ToolTimeoutUpdateRequest,
    admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db),
):
    try:
        row = await set_tool_timeout(db, tool_name, payload.timeout_seconds, updated_by=admin.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return row


@router.get("/budget", response_model=list[ToolBudgetResponse])
async def get_tool_budgets(_admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    return await list_tool_budgets(db)


@router.patch("/{tool_name}/budget", response_model=ToolBudgetResponse)
async def update_tool_budget(
    tool_name: str, payload: ToolBudgetUpdateRequest,
    admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db),
):
    try:
        row = await set_tool_budget(db, tool_name, payload.budget_limit, updated_by=admin.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return row


@router.get("/usage", response_model=list[ToolBudgetResponse])
async def get_tool_usages(_admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    return await list_tool_budgets(db)


@router.post("/{tool_name}/budget/reset", response_model=ToolBudgetResponse)
async def reset_tool_budget_endpoint(
    tool_name: str, admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db),
):
    reset = await reset_tool_budget(db, tool_name)
    if not reset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No budget configured for this tool")
    await db.commit()
    return await db.get(ToolBudget, tool_name)


@router.get("/fallback", response_model=list[ToolFallbackResponse])
async def get_tool_fallbacks(_admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    return await list_tool_fallbacks(db)


@router.post("/fallback", response_model=ToolFallbackResponse)
async def create_tool_fallback(
    payload: ToolFallbackCreateRequest, admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db),
):
    row = await set_tool_fallback(db, payload.tool_name, payload.fallback_tool, payload.priority, updated_by=admin.id)
    await db.commit()
    return row


@router.delete("/fallback/{tool_name}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_tool_fallback(tool_name: str, _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    removed = await delete_tool_fallbacks(db, tool_name)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No fallback configured for this tool")
    await db.commit()
