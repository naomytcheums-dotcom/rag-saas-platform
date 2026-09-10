"""Real Twilio SMS/WhatsApp sending. Honest gate: without
TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM_NUMBER all set, every
function raises TwilioNotConfiguredError -> a real 501, same pattern
as billing_stripe.py and airbyte_client.py -- this environment's
.env has a real Account SID but no real Auth Token yet."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.sms import SmsChannel, SmsMessage, SmsStatus


class TwilioNotConfiguredError(Exception):
    pass


class SmsMessageNotFoundError(Exception):
    pass


def _client():
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN or not settings.TWILIO_FROM_NUMBER:
        raise TwilioNotConfiguredError(
            "Twilio is not configured on this deployment -- set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
            "and TWILIO_FROM_NUMBER in .env to enable real SMS/WhatsApp sending."
        )
    from twilio.rest import Client

    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


async def send_sms(db: AsyncSession, organization_id: uuid.UUID, *, to: str, message: str, user_id: uuid.UUID | None) -> SmsMessage:
    return await _send(db, organization_id, channel=SmsChannel.sms, to=to, message=message, user_id=user_id, from_number=settings.TWILIO_FROM_NUMBER)


async def send_whatsapp(db: AsyncSession, organization_id: uuid.UUID, *, to: str, message: str, user_id: uuid.UUID | None) -> SmsMessage:
    from_number = settings.TWILIO_WHATSAPP_FROM_NUMBER or settings.TWILIO_FROM_NUMBER
    return await _send(db, organization_id, channel=SmsChannel.whatsapp, to=f"whatsapp:{to.removeprefix('whatsapp:')}", message=message, user_id=user_id, from_number=f"whatsapp:{from_number.removeprefix('whatsapp:')}" if from_number else None)


async def _send(db: AsyncSession, organization_id: uuid.UUID, *, channel: SmsChannel, to: str, message: str, user_id: uuid.UUID | None, from_number: str | None) -> SmsMessage:
    client = _client()  # raises TwilioNotConfiguredError early, before any row is created

    row = SmsMessage(organization_id=organization_id, channel=channel, to_number=to, body=message, status=SmsStatus.queued, created_by=user_id)
    db.add(row)
    await db.flush()

    try:
        result = client.messages.create(to=to, from_=from_number, body=message)
        row.status = SmsStatus.sent
        row.provider_message_id = result.sid
    except Exception as exc:  # noqa: BLE001 -- a real, honest failed-send record, not an unhandled 500
        row.status = SmsStatus.failed
        row.error = str(exc)

    await db.flush()
    return row


async def get_sms_status(db: AsyncSession, organization_id: uuid.UUID, message_id: uuid.UUID) -> SmsMessage:
    row = await db.get(SmsMessage, message_id)
    if row is None or row.organization_id != organization_id:
        raise SmsMessageNotFoundError(str(message_id))
    return row


async def list_sms_messages(db: AsyncSession, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[SmsMessage]:
    return list((await db.scalars(
        select(SmsMessage).where(SmsMessage.organization_id == organization_id).order_by(SmsMessage.created_at.desc()).limit(limit).offset(offset)
    )).all())
