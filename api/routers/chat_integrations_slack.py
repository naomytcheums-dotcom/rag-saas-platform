"""Partie 9.4.1 -- Slack integration endpoints."""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.chat_integrations import SlackIntegration
from api.models.organization import OrganizationMember
from api.schemas.chat_integrations import SlackConfigResponse, SlackConfigureRequest, SlackSendMessageRequest
from api.security.chat_integrations_signature import verify_slack_signature
from api.security.organizations import require_org_admin
from api.services.chat_integrations.slack import (
    SlackIntegrationError, get_oauth_url, handle_oauth_callback, process_slack_message, save_integration,
    send_slack_response, validate_slack_config,
)

router = APIRouter(tags=["Slack Integration"])
_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _get_integration(db: AsyncSession, org_id: uuid.UUID) -> SlackIntegration:
    integration = await db.scalar(select(SlackIntegration).where(SlackIntegration.organization_id == org_id))
    if integration is None:
        raise _NOT_FOUND
    return integration


@router.get("/organizations/{org_id}/integrations/slack/auth")
async def slack_auth_url_endpoint(org_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_admin)):
    try:
        return {"url": get_oauth_url(org_id)}
    except SlackIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/integrations/slack/callback")
async def slack_oauth_callback_endpoint(code: str, state: str, db: AsyncSession = Depends(get_db)):
    try:
        integration = await handle_oauth_callback(db, code, state, None)
    except SlackIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return {"connected": True, "team_name": integration.team_name}


@router.post("/organizations/{org_id}/integrations/slack/configure", response_model=SlackConfigResponse)
async def slack_configure_endpoint(org_id: uuid.UUID, payload: SlackConfigureRequest, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    integration = await _get_integration(db, org_id)
    data = payload.model_dump(exclude_unset=True)
    try:
        validate_slack_config(data)
    except SlackIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    for key, value in data.items():
        setattr(integration, key, value)
    await db.commit()
    return integration


@router.get("/organizations/{org_id}/integrations/slack/config", response_model=SlackConfigResponse)
async def slack_get_config_endpoint(org_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    return await _get_integration(db, org_id)


@router.delete("/organizations/{org_id}/integrations/slack")
async def slack_delete_integration_endpoint(org_id: uuid.UUID, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    integration = await _get_integration(db, org_id)
    await db.delete(integration)
    await db.commit()
    return {"deleted": True}


@router.post("/organizations/{org_id}/integrations/slack/send")
async def slack_send_endpoint(org_id: uuid.UUID, payload: SlackSendMessageRequest, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    integration = await _get_integration(db, org_id)
    return await send_slack_response(integration, payload.channel, payload.text, payload.thread_ts)


@router.post("/integrations/slack/events")
async def slack_events_endpoint(
    request: Request, db: AsyncSession = Depends(get_db),
    x_slack_signature: str | None = Header(default=None), x_slack_request_timestamp: str | None = Header(default=None),
):
    """Real Slack Events API webhook -- signature-verified (real,
    HMAC, api/security/chat_integrations_signature.py), handles the
    real `url_verification` handshake AND real `event_callback`
    messages, dispatched to the SAME real `process_slack_message`
    engine every other real entry point uses."""
    body = await request.body()
    if not verify_slack_signature(x_slack_request_timestamp, body, x_slack_signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Slack signature")

    payload = await request.json()
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    event = payload.get("event") or {}
    if payload.get("type") == "event_callback" and event.get("type") in ("message", "app_mention") and not event.get("bot_id"):
        integration = await db.scalar(select(SlackIntegration).where(SlackIntegration.team_id == payload.get("team_id")))
        if integration is not None and integration.is_active:
            await process_slack_message(db, integration, {
                "ts": event["ts"], "channel": event["channel"], "user": event.get("user", ""),
                "user_name": None, "text": event.get("text", ""), "thread_ts": event.get("thread_ts"),
            })
            await db.commit()
    return {"ok": True}
