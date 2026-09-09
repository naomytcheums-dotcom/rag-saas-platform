"""
Partie 9.1.1-9.1.9 -- the public `/v1/*` API, authenticated by a real
`X-API-Key` header (organization-scoped, see
api/security/public_api_auth.py). Every route below is scope-gated
(`require_public_api_scope`) AND rate-limited (the same dependency
enforces both at once).

Also carries the one real, necessary, additive piece the literal 9.1.x
asks never mention at all: how an organization actually GETS an API
key in the first place (`POST/GET/DELETE /organizations/{org_id}/api-keys`,
real JWT-authenticated, Admin+) -- without it, this whole public API
would be real but permanently unreachable.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.models.organization_api_key import OrganizationAPIKey
from api.schemas.public_api import (
    AgentRunRequest, AgentRunResponse, AnalyticsResponse, ChatRequest, ChatResponse, DocumentUploadResponse,
    EmbedRequest, EmbedResponse, KnowledgeBaseCreateRequest, KnowledgeBaseCreateResponse,
    OrganizationAPIKeyCreateRequest, OrganizationAPIKeyCreateResponse, OrganizationAPIKeyResponse,
    ConversationListResponse, PublicSearchRequest, PublicSearchResponse, UsageResponse,
)
from api.security.organizations import require_org_admin
from api.security.public_api_auth import require_public_api_scope
from api.services.organization_api_keys import generate_organization_api_key, list_api_keys, revoke_api_key
from api.services.public_api import (
    PublicAPIError, handle_public_agent_run, handle_public_analytics, handle_public_chat,
    handle_public_conversations_list, handle_public_document_upload, handle_public_embed, handle_public_kb_creation,
    handle_public_search, handle_public_usage,
)

router = APIRouter(tags=["Public API"])


def _to_http_error(exc: PublicAPIError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# --------------------------------------------------------- API key management (JWT)


@router.post("/organizations/{org_id}/api-keys", response_model=OrganizationAPIKeyCreateResponse)
async def create_organization_api_key_endpoint(
    org_id: uuid.UUID, payload: OrganizationAPIKeyCreateRequest,
    caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    row, plaintext_key = await generate_organization_api_key(
        db, org_id, payload.name, payload.scopes, expires_at=payload.expires_at, created_by=caller.user_id,
    )
    await db.commit()
    return OrganizationAPIKeyCreateResponse(
        id=row.id, name=row.name, key=plaintext_key, key_prefix=row.key_prefix, scopes=row.scopes,
        expires_at=row.expires_at, created_at=row.created_at,
    )


@router.get("/organizations/{org_id}/api-keys", response_model=list[OrganizationAPIKeyResponse])
async def list_organization_api_keys_endpoint(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    return await list_api_keys(db, org_id)


@router.delete("/organizations/{org_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_organization_api_key_endpoint(
    org_id: uuid.UUID, key_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    revoked = await revoke_api_key(db, key_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


# ------------------------------------------------------------------------- 9.1.1 Chat


@router.post("/v1/chat", response_model=ChatResponse)
async def public_chat_endpoint(payload: ChatRequest, key_row: OrganizationAPIKey = Depends(require_public_api_scope("chat")), db: AsyncSession = Depends(get_db)):
    try:
        result = await handle_public_chat(db, key_row, payload.message, payload.agent_id, payload.conversation_id)
    except PublicAPIError as exc:
        await db.rollback()
        raise _to_http_error(exc) from exc
    await db.commit()
    return result


# --------------------------------------------------------------------- 9.1.2 Documents


@router.post("/v1/documents", response_model=DocumentUploadResponse)
async def public_document_upload_endpoint(
    file: UploadFile, workspace_id: uuid.UUID | None = None,
    key_row: OrganizationAPIKey = Depends(require_public_api_scope("documents:write")), db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    try:
        result = await handle_public_document_upload(db, key_row, file.filename or "document", content, workspace_id)
    except PublicAPIError as exc:
        await db.rollback()
        raise _to_http_error(exc) from exc
    await db.commit()
    return result


# ---------------------------------------------------------------- 9.1.3 Knowledge bases


@router.post("/v1/knowledge-bases", response_model=KnowledgeBaseCreateResponse)
async def public_kb_creation_endpoint(
    payload: KnowledgeBaseCreateRequest, key_row: OrganizationAPIKey = Depends(require_public_api_scope("knowledge_bases:write")),
    db: AsyncSession = Depends(get_db),
):
    workspace = await handle_public_kb_creation(db, key_row, payload.name, payload.description, payload.config)
    await db.commit()
    return KnowledgeBaseCreateResponse(id=workspace.id, name=workspace.name, description=payload.description, created_at=workspace.created_at)


# -------------------------------------------------------------------- 9.1.4 Conversations


@router.get("/v1/conversations", response_model=ConversationListResponse)
async def public_conversations_list_endpoint(
    limit: int = 20, offset: int = 0, agent_id: str | None = None,
    key_row: OrganizationAPIKey = Depends(require_public_api_scope("conversations:read")), db: AsyncSession = Depends(get_db),
):
    return await handle_public_conversations_list(db, key_row.organization_id, agent_id, limit, offset)


# ------------------------------------------------------------------------ 9.1.5 Search


@router.post("/v1/search", response_model=PublicSearchResponse)
async def public_search_endpoint(
    payload: PublicSearchRequest, key_row: OrganizationAPIKey = Depends(require_public_api_scope("search")), db: AsyncSession = Depends(get_db),
):
    return await handle_public_search(db, key_row.organization_id, payload.query, payload.workspace_id, payload.filters, payload.top_k)


# --------------------------------------------------------------------- 9.1.6 Agents/run


@router.post("/v1/agents/run", response_model=AgentRunResponse)
async def public_agent_run_endpoint(
    payload: AgentRunRequest, key_row: OrganizationAPIKey = Depends(require_public_api_scope("agents:run")), db: AsyncSession = Depends(get_db),
):
    try:
        result = await handle_public_agent_run(db, key_row, payload.agent_id, payload.input, payload.conversation_id)
    except PublicAPIError as exc:
        await db.rollback()
        raise _to_http_error(exc) from exc
    await db.commit()
    return result


# ------------------------------------------------------------------------- 9.1.7 Usage


@router.get("/v1/usage", response_model=UsageResponse)
async def public_usage_endpoint(
    period: str = "month", metric: str | None = None,
    key_row: OrganizationAPIKey = Depends(require_public_api_scope("usage:read")), db: AsyncSession = Depends(get_db),
):
    return await handle_public_usage(db, key_row.organization_id, period)


# --------------------------------------------------------------------- 9.1.8 Analytics


@router.get("/v1/analytics", response_model=AnalyticsResponse)
async def public_analytics_endpoint(
    period: str = "month", metrics: str | None = None,
    key_row: OrganizationAPIKey = Depends(require_public_api_scope("analytics:read")), db: AsyncSession = Depends(get_db),
):
    requested = metrics.split(",") if metrics else None
    return await handle_public_analytics(db, key_row.organization_id, period, requested)


# ------------------------------------------------------------------------- 9.1.9 Embed


@router.post("/v1/embed", response_model=EmbedResponse)
async def public_embed_endpoint(payload: EmbedRequest, _key_row: OrganizationAPIKey = Depends(require_public_api_scope("embed"))):
    return await handle_public_embed(payload.text, payload.model)
