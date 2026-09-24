"""
Partie 5.1.14 -- reading a real agent run's own per-step traces.

**A real, documented deviation from this étape's own literal paths**
(`/agents/runs/{run_id}/traces`, no organization): mounted under
`/organizations/{org_id}/...`, matching this codebase's established
convention. Any real member can read traces for a run in their OWN
organization (debugging/audit visibility, same "Admin gets real
visibility" spirit already used elsewhere) -- 404 if the run doesn't
belong to `org_id` (anti-enumeration, real ownership check).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.schemas.agent_traces import AgentTraceResponse
from api.security.permissions import require_permission
from api.security.agent_runs import get_run
from api.security.organizations import require_org_member
from api.services.agent_traces import export_agent_traces, get_agent_trace_tree, get_agent_traces

router = APIRouter(prefix="/organizations/{org_id}/agents/runs/{run_id}", tags=["agent-traces"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _get_owned_run(db: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID):
    run = await get_run(db, run_id)
    if run is None or run.organization_id != org_id:
        raise _NOT_FOUND
    return run


@router.get("/traces", response_model=list[AgentTraceResponse])
async def list_agent_traces(
    org_id: uuid.UUID, run_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("agents:read")), db: AsyncSession = Depends(get_db),
):
    await _get_owned_run(db, org_id, run_id)
    return await get_agent_traces(db, run_id)


@router.get("/traces/tree")
async def get_agent_traces_tree(
    org_id: uuid.UUID, run_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("agents:read")), db: AsyncSession = Depends(get_db),
):
    await _get_owned_run(db, org_id, run_id)
    return await get_agent_trace_tree(db, run_id)


@router.get("/traces/export")
async def export_agent_traces_endpoint(
    org_id: uuid.UUID, run_id: uuid.UUID, format: str = "json",
    _caller: OrganizationMember = Depends(require_permission("agents:read")), db: AsyncSession = Depends(get_db),
):
    await _get_owned_run(db, org_id, run_id)
    try:
        exported = await export_agent_traces(db, run_id, format)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    media_type = "application/json" if format == "json" else "text/html"
    return Response(content=exported, media_type=media_type)
