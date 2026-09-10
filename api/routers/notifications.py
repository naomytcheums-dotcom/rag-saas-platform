"""Real Twilio SMS/WhatsApp sending, org-scoped (this codebase's
established convention -- see billing.py's own module docstring)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.schemas.notifications import SendSmsRequest, SmsMessageResponse
from api.security.organizations import require_org_admin, require_org_member
from api.services import twilio_sms

router = APIRouter(prefix="/organizations/{org_id}/notifications", tags=["Notifications"])


@router.post("/sms/send", response_model=SmsMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_sms_endpoint(org_id: uuid.UUID, body: SendSmsRequest, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        message = await twilio_sms.send_sms(db, org_id, to=body.to, message=body.message, user_id=caller.user_id)
    except twilio_sms.TwilioNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    await db.commit()
    return message


@router.post("/whatsapp/send", response_model=SmsMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_whatsapp_endpoint(org_id: uuid.UUID, body: SendSmsRequest, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        message = await twilio_sms.send_whatsapp(db, org_id, to=body.to, message=body.message, user_id=caller.user_id)
    except twilio_sms.TwilioNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    await db.commit()
    return message


@router.get("/sms", response_model=list[SmsMessageResponse])
async def list_sms_endpoint(org_id: uuid.UUID, limit: int = 50, offset: int = 0, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await twilio_sms.list_sms_messages(db, org_id, limit, offset)


@router.get("/sms/{message_id}", response_model=SmsMessageResponse)
async def get_sms_endpoint(org_id: uuid.UUID, message_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        return await twilio_sms.get_sms_status(db, org_id, message_id)
    except twilio_sms.SmsMessageNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
