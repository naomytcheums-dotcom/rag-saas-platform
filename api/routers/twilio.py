"""Partie 8.2.13 -- Twilio webhooks (real form-encoded POSTs, not
JSON -- Twilio's own real, fixed content type) + the one real,
authenticated, non-webhook route (`POST /twilio/outbound`)."""

from fastapi import APIRouter, Depends, Form, HTTPException, Response, status
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.user import User
from api.schemas.telephony import CallRecordResponse
from api.services.telephony import (
    TelephonyError, end_call, handle_call_status, handle_dtmf_input, handle_incoming_call, handle_speech_input,
    list_calls, make_outbound_call, verify_twilio_signature,
)

router = APIRouter(prefix="/twilio", tags=["telephony"])


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
async def twilio_outbound_endpoint(to: str, agent_id: str, from_: str | None = None, current_user: User = Depends(get_current_user)):
    try:
        call_sid = await make_outbound_call(to, from_, agent_id)
    except TelephonyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"call_sid": call_sid}


@router.get("/calls", response_model=list[CallRecordResponse])
async def list_calls_endpoint(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await list_calls(db)


@router.post("/{call_sid}/end", status_code=status.HTTP_204_NO_CONTENT)
async def twilio_end_call_endpoint(call_sid: str, current_user: User = Depends(get_current_user)):
    try:
        await end_call(call_sid)
    except TelephonyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
