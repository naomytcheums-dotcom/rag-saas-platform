"""
Partie 5.3.10 -- agent API key management (Manager+) and the one real,
differently-authenticated endpoint that uses one (`POST /api/agents/run`,
`X-API-Key` header, no JWT). Running through this path still goes
through `AgentOrchestrator.run_agent`'s own real permission (Partie
5.3.7) and guardrail (Partie 5.3.9) checks -- an API key is a real,
alternate way IN, never a way to bypass what already applies to every
other real caller.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.agent import Agent
from api.models.agent_api_key import AgentAPIKey
from api.models.organization import OrganizationMember
from api.schemas.agent_api_keys import (
    AgentAPIKeyCreateRequest, AgentAPIKeyCreateResponse, AgentAPIKeyResponse, AgentRunViaAPIKeyRequest,
    AgentRunViaAPIKeyResponse,
)
from api.security.agent_api_keys import require_api_key_scope
from api.security.agents import require_agent_manager
from api.services.agent_api_keys import generate_api_key, list_api_keys, revoke_api_key
from api.services.agent_orchestrator import AgentOrchestrator

router = APIRouter(tags=["agent-api-keys"])


@router.post("/agents/{agent_id}/api-keys", response_model=AgentAPIKeyCreateResponse)
async def create_agent_api_key_endpoint(
    payload: AgentAPIKeyCreateRequest,
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, caller = agent_ctx
    row, plaintext_key = await generate_api_key(
        db, agent.id, payload.name, payload.scopes, expires_at=payload.expires_at, created_by=caller.user_id,
    )
    await db.commit()
    return AgentAPIKeyCreateResponse(
        id=row.id, name=row.name, key=plaintext_key, key_prefix=row.key_prefix, scopes=row.scopes,
        expires_at=row.expires_at, created_at=row.created_at,
    )


@router.get("/agents/{agent_id}/api-keys", response_model=list[AgentAPIKeyResponse])
async def list_agent_api_keys_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    return await list_api_keys(db, agent.id)


@router.delete("/agents/{agent_id}/api-keys/{key_id}", status_code=204)
async def revoke_agent_api_key_endpoint(
    key_id: uuid.UUID,
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    key_row = await db.get(AgentAPIKey, key_id)
    if key_row is not None and key_row.agent_id == agent.id:
        await revoke_api_key(db, key_id)
        await db.commit()


@router.post("/api/agents/run", response_model=AgentRunViaAPIKeyResponse)
async def run_agent_via_api_key_endpoint(
    payload: AgentRunViaAPIKeyRequest,
    agent_ctx: tuple[Agent, AgentAPIKey] = Depends(require_api_key_scope("execute")), db: AsyncSession = Depends(get_db),
):
    agent, key_row = agent_ctx
    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent(
        str(agent.id), payload.input, db=db, context=payload.context,
        organization_id=agent.organization_id, created_by=key_row.created_by,
    )
    return AgentRunViaAPIKeyResponse(run_id=run.id, status=run.status, result=run.result, error=run.error)
