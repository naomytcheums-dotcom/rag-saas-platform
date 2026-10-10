"""Partie 8.2.13 -- Twilio webhooks (real form-encoded POSTs, not
JSON -- Twilio's own real, fixed content type) + the authenticated, non-webhook routes: tenant call management under
`/organizations/{org_id}/twilio/...` and, restricted to platform superadmins, the legacy platform-wide `/twilio/outbound|calls|{sid}/end`."""

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Response, status
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_db, require_superadmin
from api.models.audit_log import AuditAction
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.telephony import CallRecordResponse, OutboundCallRequest
from api.security.audit_log import log_audit_action
from api.security.permissions import require_permission
from api.security.rate_limit import enforce_rate_limit
from api.services.voice_usage import assert_voice_minutes_available
from api.services.telephony import (
    TelephonyError, TelephonyNotFoundError, end_call, end_organization_call, handle_call_status, handle_dtmf_input,
    handle_incoming_call, handle_speech_input, list_calls, list_organization_calls, make_outbound_call,
    place_organization_call, verify_twilio_signature,
)
from api.utils import MAX_PAGE_SIZE, client_ip

router = APIRouter(prefix="/twilio", tags=["telephony"])
org_router = APIRouter(tags=["telephony"])


async def _verify_or_403(request: Request, params: dict) -> None:
    signature = request.headers.get("X-Twilio-Signature")
    if not verify_twilio_signature(str(request.url), params, signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Twilio signature")


@router.post("/incoming")
async def twilio_incoming_endpoint(
    request: Request, agent_id: str, CallSid: str = Form(...), From: str = Form(...), To: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    await _verify_or_403(request, {"CallSid": CallSid, "From": From, "To": To})
    twiml = await handle_incoming_call(db, CallSid, From, To, agent_id)
    await db.commit()
    return Response(content=twiml, media_type="application/xml")


@router.post("/speech")
async def twilio_speech_endpoint(
    request: Request, agent_id: str, CallSid: str = Form(...), SpeechResult: str = Form(""), db: AsyncSession = Depends(get_db),
):
    await _verify_or_403(request, {"CallSid": CallSid, "SpeechResult": SpeechResult})
    twiml = await handle_speech_input(db, CallSid, SpeechResult, agent_id)
    await db.commit()
    return Response(content=twiml, media_type="application/xml")


@router.post("/dtmf")
async def twilio_dtmf_endpoint(request: Request, CallSid: str = Form(...), Digits: str = Form(""), db: AsyncSession = Depends(get_db)):
    await _verify_or_403(request, {"CallSid": CallSid, "Digits": Digits})
    twiml = await handle_dtmf_input(db, CallSid, Digits)
    await db.commit()
    return Response(content=twiml, media_type="application/xml")


@router.post("/status")
async def twilio_status_endpoint(
    request: Request, CallSid: str = Form(...), CallStatus: str = Form(...), CallDuration: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    await _verify_or_403(request, {"CallSid": CallSid, "CallStatus": CallStatus, "CallDuration": CallDuration})
    duration = int(CallDuration) if CallDuration.isdigit() else None
    await handle_call_status(db, CallSid, CallStatus, duration)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/outbound")
async def twilio_outbound_endpoint(to: str, agent_id: str, from_: str | None = None, current_user: User = Depends(require_superadmin)):
    """Platform-superadmin only. Tenants place calls through `POST /organizations/{org_id}/twilio/outbound`."""
    try:
        call_sid = await make_outbound_call(to, from_, agent_id)
    except TelephonyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"call_sid": call_sid}


@router.get("/calls", response_model=list[CallRecordResponse])
async def list_calls_endpoint(current_user: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    """Platform-superadmin only: the history of every tenant. Tenants use `GET /organizations/{org_id}/twilio/calls`."""
    return await list_calls(db)


@router.post("/{call_sid}/end", status_code=status.HTTP_204_NO_CONTENT)
async def twilio_end_call_endpoint(call_sid: str, current_user: User = Depends(require_superadmin)):
    """Platform-superadmin only. Tenants end their own calls through `POST /organizations/{org_id}/twilio/calls/{call_sid}/end`."""
    try:
        await end_call(call_sid)
    except TelephonyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@org_router.get("/organizations/{org_id}/twilio/calls", response_model=list[CallRecordResponse])
async def list_organization_calls_endpoint(
    org_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0),
    _caller: OrganizationMember = Depends(require_permission("conversations:read")), db: AsyncSession = Depends(get_db),
):
    return await list_organization_calls(db, org_id, limit, offset)


@org_router.post("/organizations/{org_id}/twilio/outbound", status_code=status.HTTP_201_CREATED, response_model=CallRecordResponse)
async def place_organization_call_endpoint(
    org_id: uuid.UUID, payload: OutboundCallRequest, request: Request,
    caller: OrganizationMember = Depends(require_permission("integrations:write")), db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        f"ratelimit:twilio_outbound:org:{org_id}", settings.TWILIO_OUTBOUND_RATE_LIMIT_MAX_ATTEMPTS, settings.TWILIO_OUTBOUND_RATE_LIMIT_WINDOW_SECONDS,
    )
    from api.security.organization_settings import get_org_settings  # noqa: PLC0415

    await assert_voice_minutes_available(db, org_id, await get_org_settings(db, org_id))
    try:
        call = await place_organization_call(db, org_id, payload.to, payload.agent_id)
    except TelephonyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    except TelephonyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.TELEPHONY_CALL_PLACED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=org_id, resource_type="call", resource_id=call.call_sid, metadata={"agent_id": str(payload.agent_id)},
    )
    await db.commit()
    return call


@org_router.post("/organizations/{org_id}/twilio/calls/{call_sid}/end", status_code=status.HTTP_204_NO_CONTENT)
async def end_organization_call_endpoint(
    org_id: uuid.UUID, call_sid: str, request: Request,
    caller: OrganizationMember = Depends(require_permission("integrations:write")), db: AsyncSession = Depends(get_db),
):
    try:
        await end_organization_call(db, org_id, call_sid)
    except TelephonyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    except TelephonyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.TELEPHONY_CALL_ENDED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=org_id, resource_type="call", resource_id=call_sid,
    )
    await db.commit()
