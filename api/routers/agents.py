"""
Partie 5.3.1 -- real agent CRUD + status transitions. Create/list are
org-scoped (`require_org_manager`/`require_org_member`, same tier
convention as `api/routers/workspaces.py`); get/update/delete/status
transitions resolve the agent AND the caller's real organization role
together (`require_agent_member`/`require_agent_manager`,
api/security/agents.py), since this étape's own literal paths for
those (`GET/PATCH/DELETE /agents/{agent_id}`) carry no `{org_id}`.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.agent import Agent
from api.models.organization import Organization, OrganizationMember
from api.models.user import User
from api.schemas.agents import (
    AgentCreateRequest, AgentKnowledgeBaseResponse, AgentKnowledgeBaseUpdateRequest, AgentMemoryClearResponse,
    AgentMemoryConfigResponse, AgentMemoryConfigUpdateRequest, AgentMemoryUsageResponse, AgentModelResponse,
    AgentModelUpdateRequest, AgentResponse, AgentToolsResponse, AgentToolsUpdateRequest, AgentUpdateRequest,
    KnowledgeBaseOption, SystemPromptPreviewResponse, SystemPromptUpdateRequest, SystemPromptVariablesResponse,
    ToolConfigUpdateRequest,
)
from api.security.agents import (
    activate_agent, archive_agent, create_agent, delete_agent, list_agents, pause_agent, require_agent_manager,
    require_agent_member, update_agent,
)
from api.security.organizations import require_org_manager, require_org_member
from api.security.quotas import require_quota_available
from api.services.agent_knowledge_base import (
    AgentKnowledgeBaseError, get_agent_kb_config, get_available_knowledge_bases, set_agent_knowledge_base,
)
from api.services.agent_memory_config import (
    AgentMemoryConfigError, clear_agent_memory, get_agent_memory_config, get_memory_usage, set_agent_memory_config,
)
from api.services.agent_models import (
    AgentModelError, get_agent_model, get_available_models, set_agent_model,
)
from api.services.agent_prompts import get_system_prompt_variables, preview_system_prompt
from api.services.agent_tools import (
    AgentToolError, disable_tool, enable_tool, get_agent_tools, get_available_tools, set_agent_tools,
)

router = APIRouter(tags=["agents"])


@router.post("/organizations/{org_id}/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_endpoint(
    org_id: uuid.UUID, payload: AgentCreateRequest,
    caller: OrganizationMember = Depends(require_org_manager), db: AsyncSession = Depends(get_db),
):
    await require_quota_available(db, org_id, "agents")  # Partie 1.3.6, real live count since Partie 5.3.1
    try:
        agent = await create_agent(db, org_id, payload.model_dump(by_alias=True), caller.user_id)
    except (AgentKnowledgeBaseError, AgentToolError, AgentMemoryConfigError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/organizations/{org_id}/agents", response_model=list[AgentResponse])
async def list_agents_endpoint(
    org_id: uuid.UUID, status_filter: str | None = Query(default=None, alias="status"), workspace_id: uuid.UUID | None = None,
    limit: int = Query(default=50, le=200), offset: int = Query(default=0, ge=0),
    _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db),
):
    filters = {}
    if status_filter is not None:
        filters["status"] = status_filter
    if workspace_id is not None:
        filters["workspace_id"] = workspace_id
    return await list_agents(db, org_id, filters=filters, limit=limit, offset=offset)


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent_endpoint(agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_member)):
    agent, _caller = agent_ctx
    return agent


@router.patch("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent_endpoint(
    payload: AgentUpdateRequest,
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    try:
        updated = await update_agent(db, agent.id, payload.model_dump(by_alias=True, exclude_unset=True))
    except (AgentKnowledgeBaseError, AgentToolError, AgentMemoryConfigError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(updated)
    return updated


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    await delete_agent(db, agent.id)
    await db.commit()


@router.post("/agents/{agent_id}/activate", response_model=AgentResponse)
async def activate_agent_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    updated = await activate_agent(db, agent.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/agents/{agent_id}/pause", response_model=AgentResponse)
async def pause_agent_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    updated = await pause_agent(db, agent.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/agents/{agent_id}/archive", response_model=AgentResponse)
async def archive_agent_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    updated = await archive_agent(db, agent.id)
    await db.commit()
    await db.refresh(updated)
    return updated


# ------------------------------------- Partie 5.3.2 -- system prompt templating -------------------------------------


@router.get("/agents/{agent_id}/system-prompt/preview", response_model=SystemPromptPreviewResponse)
async def preview_system_prompt_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_member),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    organization = await db.get(Organization, agent.organization_id)
    context = {
        "user_name": current_user.full_name or current_user.email,
        "organization_name": organization.name if organization else "",
        "context": "[conversation context would appear here]",
        "tools": ", ".join(t.get("name", "") for t in agent.tools) if agent.tools else "(none configured)",
        "knowledge_base": str(agent.knowledge_base_id) if agent.knowledge_base_id else "(none configured)",
    }
    return SystemPromptPreviewResponse(rendered=preview_system_prompt(agent, context))


@router.patch("/agents/{agent_id}/system-prompt", response_model=AgentResponse)
async def update_system_prompt_endpoint(
    payload: SystemPromptUpdateRequest,
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    updated = await update_agent(db, agent.id, payload.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(updated)
    return updated


@router.get("/agents/{agent_id}/system-prompt/variables", response_model=SystemPromptVariablesResponse)
async def get_system_prompt_variables_endpoint(agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_member)):
    agent, _caller = agent_ctx
    return SystemPromptVariablesResponse(variables=get_system_prompt_variables(agent))


# ------------------------------------- Partie 5.3.3 -- LLM model selection -------------------------------------


@router.get("/agents/{agent_id}/model", response_model=AgentModelResponse)
async def get_agent_model_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_member), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    return await get_agent_model(db, agent.id)


@router.patch("/agents/{agent_id}/model", response_model=AgentModelResponse)
async def update_agent_model_endpoint(
    payload: AgentModelUpdateRequest,
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    try:
        await set_agent_model(db, agent.id, payload.provider, payload.model, payload.temperature, payload.max_tokens, payload.top_p)
    except AgentModelError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return await get_agent_model(db, agent.id)


@router.get("/models")
async def list_all_models_endpoint(_current_user: User = Depends(get_current_user)):
    # Real, deliberate deviation: "Member+" has no real organization to
    # check against on this literal, org-less path -- any real,
    # authenticated user can read this real, static, non-secret model
    # catalog.
    return get_available_models()


@router.get("/models/{provider}")
async def list_provider_models_endpoint(provider: str, _current_user: User = Depends(get_current_user)):
    try:
        return get_available_models(provider)
    except AgentModelError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ------------------------------------- Partie 5.3.4 -- knowledge base selection -------------------------------------


@router.get("/agents/{agent_id}/knowledge-base", response_model=AgentKnowledgeBaseResponse)
async def get_agent_knowledge_base_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_member), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    config = await get_agent_kb_config(db, agent.id)
    return AgentKnowledgeBaseResponse(knowledge_base_id=agent.knowledge_base_id, config=config)


@router.patch("/agents/{agent_id}/knowledge-base", response_model=AgentKnowledgeBaseResponse)
async def update_agent_knowledge_base_endpoint(
    payload: AgentKnowledgeBaseUpdateRequest,
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    # A real, given `knowledge_base_id` is honored (including an
    # explicit `null` to unset it); an OMITTED one leaves the agent's
    # current real value untouched (this étape's own PATCH can update
    # just `config` alone).
    fields_set = payload.model_fields_set
    knowledge_base_id = payload.knowledge_base_id if "knowledge_base_id" in fields_set else agent.knowledge_base_id
    try:
        await set_agent_knowledge_base(db, agent.id, knowledge_base_id, payload.config)
    except AgentKnowledgeBaseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(agent)
    config = await get_agent_kb_config(db, agent.id)
    return AgentKnowledgeBaseResponse(knowledge_base_id=agent.knowledge_base_id, config=config)


@router.get("/agents/{agent_id}/knowledge-base/config")
async def get_agent_kb_config_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_member), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    return await get_agent_kb_config(db, agent.id)


@router.get("/agents/{agent_id}/knowledge-base/options", response_model=list[KnowledgeBaseOption])
async def list_agent_knowledge_base_options_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_member), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    return await get_available_knowledge_bases(db, agent.organization_id)


# ------------------------------------- Partie 5.3.5 -- tool selection -------------------------------------


@router.get("/agents/{agent_id}/tools", response_model=AgentToolsResponse)
async def get_agent_tools_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_member), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    return AgentToolsResponse(tools=await get_agent_tools(db, agent.id))


@router.patch("/agents/{agent_id}/tools", response_model=AgentToolsResponse)
async def update_agent_tools_endpoint(
    payload: AgentToolsUpdateRequest,
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    try:
        await set_agent_tools(db, agent.id, [t.model_dump() for t in payload.tools])
    except AgentToolError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return AgentToolsResponse(tools=await get_agent_tools(db, agent.id))


@router.post("/agents/{agent_id}/tools/{tool_name}/enable", response_model=AgentToolsResponse)
async def enable_agent_tool_endpoint(
    tool_name: str, payload: ToolConfigUpdateRequest,
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    try:
        await enable_tool(db, agent.id, tool_name, payload.config)
    except AgentToolError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return AgentToolsResponse(tools=await get_agent_tools(db, agent.id))


@router.post("/agents/{agent_id}/tools/{tool_name}/disable", response_model=AgentToolsResponse)
async def disable_agent_tool_endpoint(
    tool_name: str,
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    await disable_tool(db, agent.id, tool_name)
    await db.commit()
    return AgentToolsResponse(tools=await get_agent_tools(db, agent.id))


@router.get("/tools/available")
async def list_available_tools_endpoint(_current_user: User = Depends(get_current_user)):
    # Real, deliberate deviation, same reasoning as GET /models
    # (Partie 5.3.3): this literal path has no {org_id} to check
    # membership against -- any real, authenticated user can read this
    # real, static, non-secret tool catalog.
    return get_available_tools()


# ------------------------------------- Partie 5.3.6 -- memory configuration -------------------------------------


@router.get("/agents/{agent_id}/memory-config", response_model=AgentMemoryConfigResponse)
async def get_agent_memory_config_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_member), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    return await get_agent_memory_config(db, agent.id)


@router.patch("/agents/{agent_id}/memory-config", response_model=AgentMemoryConfigResponse)
async def update_agent_memory_config_endpoint(
    payload: AgentMemoryConfigUpdateRequest,
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    try:
        await set_agent_memory_config(db, agent.id, **payload.model_dump(exclude_unset=True))
    except AgentMemoryConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return await get_agent_memory_config(db, agent.id)


@router.get("/agents/{agent_id}/memory-usage", response_model=AgentMemoryUsageResponse)
async def get_agent_memory_usage_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_member), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    return await get_memory_usage(db, agent.id)


@router.post("/agents/{agent_id}/memory/clear", response_model=AgentMemoryClearResponse)
async def clear_agent_memory_endpoint(
    agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    cleared = await clear_agent_memory(db, agent.id)
    await db.commit()
    return AgentMemoryClearResponse(cleared_items=cleared)
