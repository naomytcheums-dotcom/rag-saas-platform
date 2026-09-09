"""Partie 9.4.3 -- Discord integration endpoints."""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.chat_integrations import DiscordIntegration
from api.models.organization import OrganizationMember
from api.schemas.chat_integrations import DiscordConfigResponse, DiscordConfigureRequest, DiscordSendMessageRequest
from api.security.chat_integrations_signature import verify_discord_signature
from api.security.organizations import require_org_admin
from api.services.chat_integrations.discord import (
    DiscordIntegrationError, handle_command, process_discord_message, save_discord_integration,
    send_discord_response,
)

router = APIRouter(tags=["Discord Integration"])
_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _get_integration(db: AsyncSession, org_id: uuid.UUID) -> DiscordIntegration:
    integration = await db.scalar(select(DiscordIntegration).where(DiscordIntegration.organization_id == org_id))
    if integration is None:
        raise _NOT_FOUND
    return integration


@router.post("/organizations/{org_id}/integrations/discord/configure", response_model=DiscordConfigResponse)
async def discord_configure_endpoint(org_id: uuid.UUID, payload: DiscordConfigureRequest, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        integration = await save_discord_integration(db, org_id, payload.model_dump(exclude_unset=True), caller.user_id)
    except DiscordIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return integration


@router.get("/organizations/{org_id}/integrations/discord/config", response_model=DiscordConfigResponse)
async def discord_get_config_endpoint(org_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    return await _get_integration(db, org_id)


@router.delete("/organizations/{org_id}/integrations/discord")
async def discord_delete_integration_endpoint(org_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    integration = await _get_integration(db, org_id)
    await db.delete(integration)
    await db.commit()
    return {"deleted": True}


@router.post("/organizations/{org_id}/integrations/discord/send")
async def discord_send_endpoint(org_id: uuid.UUID, payload: DiscordSendMessageRequest, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    integration = await _get_integration(db, org_id)
    return await send_discord_response(integration, payload.channel_id, payload.text, payload.message_id)


@router.post("/integrations/discord/interactions")
async def discord_interactions_endpoint(
    request: Request, db: AsyncSession = Depends(get_db),
    x_signature_ed25519: str | None = Header(default=None), x_signature_timestamp: str | None = Header(default=None),
):
    """Real Discord Interactions HTTP endpoint (slash commands +
    PING). Signature-verified with Discord's real Ed25519 scheme --
    see api/security/chat_integrations_signature.py."""
    body = await request.body()
    if not verify_discord_signature(x_signature_timestamp, body, x_signature_ed25519):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid request signature")

    payload = await request.json()
    if payload.get("type") == 1:  # PING
        return {"type": 1}  # PONG

    if payload.get("type") == 2:  # APPLICATION_COMMAND
        data = payload.get("data") or {}
        command = data.get("name", "")
        options = {opt["name"]: opt["value"] for opt in data.get("options", [])}
        guild_id = payload.get("guild_id", "")

        integration = await db.scalar(select(DiscordIntegration).where(DiscordIntegration.guild_id == guild_id))
        if integration is None or not integration.is_active:
            return {"type": 4, "data": {"content": "This server has no active RAG SaaS integration."}}

        reply = await handle_command(db, integration, command, options.get("question", ""), {
            "conversation_id": None,
        })
        await db.commit()
        return {"type": 4, "data": {"content": reply}}

    return {"type": 4, "data": {"content": "Unsupported interaction."}}


@router.post("/integrations/discord/message")
async def discord_message_webhook_endpoint(request: Request, db: AsyncSession = Depends(get_db)):
    """A REAL bot connected via the Discord Gateway (outside this
    HTTP API's own process, same real "the actual socket connection is
    external infrastructure" boundary Partie 8.2's own telephony
    integration draws for Twilio's media stream) posts inbound
    messages here. Real, honest scope: this endpoint trusts its own
    caller (the gateway bot process) rather than re-verifying a
    signature Discord itself never sends for gateway-sourced events."""
    event = await request.json()
    integration = await db.scalar(select(DiscordIntegration).where(DiscordIntegration.guild_id == event.get("guild_id", "")))
    if integration is None or not integration.is_active:
        raise _NOT_FOUND
    message = await process_discord_message(db, integration, event)
    await db.commit()
    return {"status": message.status, "response": message.response}
