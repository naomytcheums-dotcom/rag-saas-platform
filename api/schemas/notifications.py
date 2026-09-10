"""Request/response bodies for real Twilio SMS/WhatsApp sending."""

import datetime as dt
import uuid

from pydantic import BaseModel

from api.models.sms import SmsChannel, SmsStatus


class SendSmsRequest(BaseModel):
    to: str
    message: str


class SmsMessageResponse(BaseModel):
    id: uuid.UUID
    channel: SmsChannel
    to_number: str
    body: str
    status: SmsStatus
    provider_message_id: str | None
    error: str | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}
