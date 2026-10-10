"""Spec 12.3.6 -- voice minutes per month.

Minutes are counted from what is recorded: finished and ongoing phone calls (`call_records.duration_seconds`) plus stored voice messages of the
organization's conversations (`voice_messages.duration_ms`). Voice-agent turns are billed per turn in credits and are not part of this meter.

The monthly limit comes from the organization setting `voice_minutes_per_month` (set from the plan; None = unlimited). It is checked BEFORE a new call
is placed or a voice-agent turn is served, so an organization can overshoot by at most the length of the call in progress."""

import datetime as dt
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.conversation import Conversation
from api.models.voice import CallRecord, VoiceMessage


def month_start(now: dt.datetime | None = None) -> dt.datetime:
    now = now or dt.datetime.now(dt.timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def voice_minutes_used(db: AsyncSession, organization_id: uuid.UUID, now: dt.datetime | None = None) -> float:
    since = month_start(now)
    call_seconds = await db.scalar(
        select(func.coalesce(func.sum(CallRecord.duration_seconds), 0)).where(CallRecord.organization_id == organization_id, CallRecord.started_at >= since)
    ) or 0
    message_ms = await db.scalar(
        select(func.coalesce(func.sum(VoiceMessage.duration_ms), 0))
        .join(Conversation, Conversation.id == VoiceMessage.conversation_id)
        .where(Conversation.organization_id == organization_id, VoiceMessage.created_at >= since)
    ) or 0
    return round(call_seconds / 60 + message_ms / 60000, 2)


async def voice_usage_summary(db: AsyncSession, organization_id: uuid.UUID, org_settings: dict, now: dt.datetime | None = None) -> dict:
    used = await voice_minutes_used(db, organization_id, now)
    limit = org_settings.get("voice_minutes_per_month")
    limit = limit if isinstance(limit, int) and not isinstance(limit, bool) and limit >= 0 else None
    return {"used_minutes": used, "limit_minutes": limit, "remaining_minutes": None if limit is None else round(max(limit - used, 0), 2), "period_start": month_start(now)}


async def assert_voice_minutes_available(db: AsyncSession, organization_id: uuid.UUID, org_settings: dict) -> None:
    """Raise 429 when the organization has used up its monthly voice minutes."""
    summary = await voice_usage_summary(db, organization_id, org_settings)
    if summary["limit_minutes"] is not None and summary["used_minutes"] >= summary["limit_minutes"]:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Monthly voice minutes exhausted ({summary['limit_minutes']} minutes)")
