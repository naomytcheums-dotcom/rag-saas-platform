"""Partie 9.4.2 -- Microsoft Teams integration endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.audit_log import AuditAction
from api.models.chat_integrations import TeamsIntegration
from api.models.organization import OrganizationMember
from api.schemas.chat_integrations import TeamsConfigResponse, TeamsConfigureRequest, TeamsSendMessageRequest
from api.security.permissions import require_permission
from api.security.audit_log import log_audit_action
from api.security.organizations import require_org_admin
from api.utils import client_ip
from api.services.chat_integrations.teams import (
    TeamsIntegrationError, parse_teams_webhook, process_teams_message, save_teams_integration, send_teams_response,
)

router = APIRouter(tags=["Teams Integration"])
_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _get_integration(db: AsyncSession, org_id: uuid.UUID) -> TeamsIntegration:
    integration = await db.scalar(select(TeamsIntegration).where(TeamsIntegration.organization_id == org_id))
    if integration is None:
        raise _NOT_FOUND
    return integration


@router.post("/organizations/{org_id}/integrations/teams/configure", response_model=TeamsConfigResponse)
async def teams_configure_endpoint(org_id: uuid.UUID, payload: TeamsConfigureRequest, request: Request, caller: OrganizationMember = Depends(require_permission("integrations:manage")), db: AsyncSession = Depends(get_db)):
    try:
        integration = await save_teams_integration(db, org_id, payload.model_dump(exclude_unset=True), caller.user_id)
    except TeamsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.INTEGRATION_CONNECTED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=org_id, resource_type="teams_integration", resource_id=str(org_id),
    )
    await db.commit()
    return integration


@router.get("/organizations/{org_id}/integrations/teams/config", response_model=TeamsConfigResponse)
async def teams_get_config_endpoint(org_id: uuid.UUID, caller: OrganizationMember = Depends(require_permission("integrations:manage")), db: AsyncSession = Depends(get_db)):
    return await _get_integration(db, org_id)


@router.delete("/organizations/{org_id}/integrations/teams")
async def teams_delete_integration_endpoint(org_id: uuid.UUID, request: Request, caller: OrganizationMember = Depends(require_permission("integrations:manage")), db: AsyncSession = Depends(get_db)):
    integration = await _get_integration(db, org_id)
    await db.delete(integration)
    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.INTEGRATION_DISCONNECTED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=org_id, resource_type="teams_integration", resource_id=str(org_id),
    )
    await db.commit()
    return {"deleted": True}


@router.post("/organizations/{org_id}/integrations/teams/send")
async def teams_send_endpoint(org_id: uuid.UUID, payload: TeamsSendMessageRequest, caller: OrganizationMember = Depends(require_permission("integrations:manage")), db: AsyncSession = Depends(get_db)):
    integration = await _get_integration(db, org_id)
    try:
        return await send_teams_response(integration, payload.channel, payload.text, payload.reply_to_id)
    except TeamsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/integrations/teams/webhook")
async def teams_webhook_endpoint(request: Request, db: AsyncSession = Depends(get_db)):
    """Real Bot Framework Activity webhook. ⚠️ Honest limitation: no
    real, live JWKS-backed bearer-token verification here yet -- see
    api/services/chat_integrations/teams.py's own top docstring."""
    payload = await request.json()
    if payload.get("type") != "message":
        return {"ok": True}

    event = parse_teams_webhook(payload)
    tenant_id = ((payload.get("channelData") or {}).get("tenant") or {}).get("id")
    integration = await db.scalar(select(TeamsIntegration).where(TeamsIntegration.tenant_id == tenant_id)) if tenant_id else None
    if integration is not None and integration.is_active:
        await process_teams_message(db, integration, event)
        await db.commit()
    return {"ok": True}
