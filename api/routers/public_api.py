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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.audit_log import AuditAction
from api.models.organization import OrganizationMember
from api.models.organization_api_key import OrganizationAPIKey
from api.schemas.public_api import (
    AgentRunRequest, AgentRunResponse, AnalyticsResponse, AvailableScopesResponse, ChatRequest, ChatResponse,
    DocumentUploadResponse, EmbedRequest, EmbedResponse, KeyRotationHistoryResponse, KnowledgeBaseCreateRequest,
    KnowledgeBaseCreateResponse, OrganizationAPIKeyCreateRequest, OrganizationAPIKeyCreateResponse,
    OrganizationAPIKeyResponse, OrganizationAPIKeyUpdateRequest, ConversationListResponse, PublicSearchRequest,
    PublicSearchResponse, QuotaRequest, QuotaStatusResponse, RateLimitRequest, RateLimitResponse, RotateKeyRequest,
    RotateKeyResponse, ScheduleRotationRequest, ScopesUpdateRequest, SetExpirationRequest, UsageResponse,
)
from api.dependencies import get_current_user
from api.models.user import User
from api.security.audit_log import log_audit_action
from api.security.organizations import require_org_admin
from api.security.public_api_auth import require_key_org_admin, require_public_api_scope
from api.utils import PUBLIC_MAX_PAGE_SIZE, client_ip
from api.services.organization_api_keys import (
    generate_organization_api_key, get_available_scopes, get_expiring_keys,
    get_key_rotation_history, get_quota_status, get_rate_limit_status, list_api_keys, OrganizationAPIKeyError,
    remove_key_expiration, revoke_api_key, rotate_api_key, schedule_key_rotation, set_key_expiration, set_quota,
    set_rate_limit, update_api_key,
)
from api.services.public_api import (
    PublicAPIError, handle_public_agent_run, handle_public_agents_list, handle_public_analytics, handle_public_chat,
    handle_public_conversations_list, handle_public_document_upload, handle_public_documents_list,
    handle_public_embed, handle_public_kb_creation, handle_public_kb_list, handle_public_search, handle_public_usage,
    require_owner,
)

router = APIRouter(tags=["Public API"])


def _to_http_error(exc: PublicAPIError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# --------------------------------------------------------- API key management (JWT)


@router.post("/organizations/{org_id}/api-keys", response_model=OrganizationAPIKeyCreateResponse)
async def create_organization_api_key_endpoint(
    org_id: uuid.UUID, payload: OrganizationAPIKeyCreateRequest, request: Request,
    caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    try:
        row, plaintext_key = await generate_organization_api_key(
            db, org_id, payload.name, payload.scopes, expires_at=payload.expires_at, created_by=caller.user_id,
        )
    except OrganizationAPIKeyError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.API_KEY_CREATED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=org_id, resource_type="api_key", resource_id=str(row.id), metadata={"name": row.name},
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
    org_id: uuid.UUID, key_id: uuid.UUID, request: Request, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    revoked = await revoke_api_key(db, key_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.API_KEY_DELETED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=org_id, resource_type="api_key", resource_id=str(key_id),
    )
    await db.commit()


_KEY_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


# Real, static single-segment routes registered BEFORE `/api-keys/{key_id}`
# below -- Starlette matches routes in real registration order, and a
# static path declared AFTER a real `{key_id}: uuid.UUID` route would
# real-ily 422 (an unparsable UUID) instead of ever reaching these
# (same real routing note as api/routers/conversations.py's own
# `/search`/`/stats`/`/deleted` routes, Partie 8.1.10-8.1.12).


@router.get("/api-keys/scopes", response_model=AvailableScopesResponse)
async def list_available_scopes_endpoint(_current_user: User = Depends(get_current_user)):
    """Real, deliberately open to any authenticated user (not
    Admin+-gated): this is a real, static, non-sensitive, global list
    -- not a real, per-organization resource."""
    return AvailableScopesResponse(scopes=list(get_available_scopes()))


@router.get("/organizations/{org_id}/api-keys/expiring", response_model=list[OrganizationAPIKeyResponse])
async def get_expiring_keys_endpoint(
    org_id: uuid.UUID, days: int = 30, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    """Real, deliberately org-scoped path (`/organizations/{org_id}/...`,
    not a bare `/api-keys/expiring`) -- see
    `get_expiring_keys`'s own docstring for the real security fix this
    real scoping requires."""
    return await get_expiring_keys(db, days, organization_id=org_id)


@router.get("/api-keys/{key_id}", response_model=OrganizationAPIKeyResponse)
async def get_api_key_endpoint(key_row: OrganizationAPIKey = Depends(require_key_org_admin)):
    return key_row


@router.patch("/api-keys/{key_id}", response_model=OrganizationAPIKeyResponse)
async def update_api_key_endpoint(
    payload: OrganizationAPIKeyUpdateRequest, key_row: OrganizationAPIKey = Depends(require_key_org_admin), db: AsyncSession = Depends(get_db),
):
    try:
        row = await update_api_key(db, key_row.id, name=payload.name, scopes=payload.scopes, is_active=payload.is_active)
    except OrganizationAPIKeyError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return row


# ------------------------------------------------------------------ 9.2.2 Key rotation


@router.post("/api-keys/{key_id}/rotate", response_model=RotateKeyResponse)
async def rotate_api_key_endpoint(
    request: Request,
    payload: RotateKeyRequest = RotateKeyRequest(),
    key_row: OrganizationAPIKey = Depends(require_key_org_admin), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    result = await rotate_api_key(db, key_row.id, rotated_by=current_user.id, reason=payload.reason)
    if result is None:
        raise _KEY_NOT_FOUND
    new_row, plaintext_key = result
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.API_KEY_ROTATED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=key_row.organization_id, resource_type="api_key", resource_id=str(new_row.id),
    )
    await db.commit()
    return RotateKeyResponse(
        id=new_row.id, name=new_row.name, key=plaintext_key, key_prefix=new_row.key_prefix, scopes=new_row.scopes,
        expires_at=new_row.expires_at, created_at=new_row.created_at,
    )


@router.get("/api-keys/{key_id}/rotation-history", response_model=list[KeyRotationHistoryResponse])
async def get_key_rotation_history_endpoint(key_row: OrganizationAPIKey = Depends(require_key_org_admin), db: AsyncSession = Depends(get_db)):
    return await get_key_rotation_history(db, key_row.id)


@router.post("/api-keys/{key_id}/schedule-rotation", response_model=OrganizationAPIKeyResponse)
async def schedule_key_rotation_endpoint(
    payload: ScheduleRotationRequest, key_row: OrganizationAPIKey = Depends(require_key_org_admin), db: AsyncSession = Depends(get_db),
):
    row = await schedule_key_rotation(db, key_row.id, payload.rotate_at)
    await db.commit()
    return row


# --------------------------------------------------------------- 9.2.3 Key expiration


@router.patch("/api-keys/{key_id}/expiration", response_model=OrganizationAPIKeyResponse)
async def set_key_expiration_endpoint(
    payload: SetExpirationRequest, key_row: OrganizationAPIKey = Depends(require_key_org_admin), db: AsyncSession = Depends(get_db),
):
    row = await set_key_expiration(db, key_row.id, payload.expires_at)
    await db.commit()
    return row


@router.delete("/api-keys/{key_id}/expiration", response_model=OrganizationAPIKeyResponse)
async def remove_key_expiration_endpoint(key_row: OrganizationAPIKey = Depends(require_key_org_admin), db: AsyncSession = Depends(get_db)):
    row = await remove_key_expiration(db, key_row.id)
    await db.commit()
    return row


# ------------------------------------------------------------------- 9.2.5 Rate limits


@router.get("/api-keys/{key_id}/rate-limit", response_model=RateLimitResponse)
async def get_rate_limit_endpoint(key_row: OrganizationAPIKey = Depends(require_key_org_admin)):
    return await get_rate_limit_status(key_row)


@router.patch("/api-keys/{key_id}/rate-limit", response_model=OrganizationAPIKeyResponse)
async def set_rate_limit_endpoint(
    payload: RateLimitRequest, key_row: OrganizationAPIKey = Depends(require_key_org_admin), db: AsyncSession = Depends(get_db),
):
    try:
        row = await set_rate_limit(db, key_row.id, payload.limit, payload.period)
    except OrganizationAPIKeyError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return row


# ----------------------------------------------------------------------- 9.2.6 Quotas


@router.get("/api-keys/{key_id}/quota", response_model=QuotaStatusResponse)
async def get_quota_endpoint(key_row: OrganizationAPIKey = Depends(require_key_org_admin)):
    return await get_quota_status(key_row)


@router.patch("/api-keys/{key_id}/quota", response_model=OrganizationAPIKeyResponse)
async def set_quota_endpoint(
    payload: QuotaRequest, key_row: OrganizationAPIKey = Depends(require_key_org_admin), db: AsyncSession = Depends(get_db),
):
    try:
        row = await set_quota(db, key_row.id, payload.limit, payload.period)
    except OrganizationAPIKeyError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return row


@router.get("/api-keys/{key_id}/quota/status", response_model=QuotaStatusResponse)
async def get_quota_status_endpoint(key_row: OrganizationAPIKey = Depends(require_key_org_admin)):
    return await get_quota_status(key_row)


# ------------------------------------------------------------------------- 9.2.4 Scopes


@router.patch("/api-keys/{key_id}/scopes", response_model=OrganizationAPIKeyResponse)
async def update_key_scopes_endpoint(
    payload: ScopesUpdateRequest, key_row: OrganizationAPIKey = Depends(require_key_org_admin), db: AsyncSession = Depends(get_db),
):
    try:
        row = await update_api_key(db, key_row.id, scopes=payload.scopes)
    except OrganizationAPIKeyError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if row is None:
        raise _KEY_NOT_FOUND
    await db.commit()
    return row


# ------------------------------------------------------------------------- 9.1.1 Chat


@router.post("/v1/chat", response_model=ChatResponse)
async def public_chat_endpoint(payload: ChatRequest, key_row: OrganizationAPIKey = Depends(require_public_api_scope("chat:write")), db: AsyncSession = Depends(get_db)):
    try:
        result = await handle_public_chat(db, key_row.organization_id, require_owner(key_row), payload.message, payload.agent_id, payload.conversation_id)
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
    payload: KnowledgeBaseCreateRequest, key_row: OrganizationAPIKey = Depends(require_public_api_scope("kb:write")),
    db: AsyncSession = Depends(get_db),
):
    workspace = await handle_public_kb_creation(db, key_row, payload.name, payload.description, payload.config)
    await db.commit()
    return KnowledgeBaseCreateResponse(id=workspace.id, name=workspace.name, description=payload.description, created_at=workspace.created_at)


# -------------------------------------------------------------------- 9.1.4 Conversations


@router.get("/v1/conversations", response_model=ConversationListResponse)
async def public_conversations_list_endpoint(
    limit: int = Query(default=20, ge=1, le=PUBLIC_MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0), agent_id: str | None = None,
    key_row: OrganizationAPIKey = Depends(require_public_api_scope("chat:read")), db: AsyncSession = Depends(get_db),
):
    return await handle_public_conversations_list(db, key_row.organization_id, agent_id, limit, offset)


# ------------------------------------------------------------------------ 9.1.5 Search


@router.post("/v1/search", response_model=PublicSearchResponse)
async def public_search_endpoint(
    payload: PublicSearchRequest, key_row: OrganizationAPIKey = Depends(require_public_api_scope("search:read")), db: AsyncSession = Depends(get_db),
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
async def public_embed_endpoint(payload: EmbedRequest, _key_row: OrganizationAPIKey = Depends(require_public_api_scope("embed:write"))):
    return await handle_public_embed(payload.text, payload.model)


# ------------------------------------------------------- Additive: read-only listings
#
# Real, additive: `documents:read`/`agents:read`/`kb:read` are all real
# scopes in 9.2.4's own table, but no literal 9.1.x ask ever gives them
# a real endpoint to actually gate -- without these, granting a real
# caller one of these 3 real scopes would do nothing at all.


@router.get("/v1/documents")
async def public_documents_list_endpoint(
    limit: int = Query(default=20, ge=1, le=PUBLIC_MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0),
    key_row: OrganizationAPIKey = Depends(require_public_api_scope("documents:read")),
    db: AsyncSession = Depends(get_db),
):
    return await handle_public_documents_list(db, key_row.organization_id, limit, offset)


@router.get("/v1/agents")
async def public_agents_list_endpoint(
    limit: int = Query(default=20, ge=1, le=PUBLIC_MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0),
    key_row: OrganizationAPIKey = Depends(require_public_api_scope("agents:read")),
    db: AsyncSession = Depends(get_db),
):
    return await handle_public_agents_list(db, key_row.organization_id, limit, offset)


@router.get("/v1/knowledge-bases")
async def public_kb_list_endpoint(
    limit: int = Query(default=20, ge=1, le=PUBLIC_MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0),
    key_row: OrganizationAPIKey = Depends(require_public_api_scope("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    return await handle_public_kb_list(db, key_row.organization_id, limit, offset)
