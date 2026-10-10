"""Spec 12.3.6 -- monthly voice minutes meter and limit. Fast SQLite suite."""

import datetime as dt
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from api.models.conversation import Conversation
from api.models.user import User
from api.models.voice import CallRecord, VoiceMessage
from api.services.voice_usage import assert_voice_minutes_available, month_start, voice_minutes_used, voice_usage_summary


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _org(client, db_session, email="voice-owner@example.com"):
    token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    org = (await client.post("/organizations", json={"name": "Voice Org"}, headers=_h(token))).json()
    return token, user, uuid.UUID(org["id"])


async def _add_usage(db_session, user, org_id, call_seconds=0, message_ms=0, when=None):
    when = when or dt.datetime.now(dt.timezone.utc)
    if call_seconds:
        db_session.add(CallRecord(call_sid=f"CA{uuid.uuid4().hex}", organization_id=org_id, from_number="+1", to_number="+2", duration_seconds=call_seconds, started_at=when))
    if message_ms:
        conv = Conversation(agent_id="a", user_id=user.id, organization_id=org_id, title="v")
        db_session.add(conv)
        await db_session.flush()
        db_session.add(VoiceMessage(conversation_id=conv.id, user_id=user.id, type="user", duration_ms=message_ms, created_at=when))
    await db_session.commit()


async def test_minutes_add_up_calls_and_voice_messages_of_this_month_only(client, db_session):
    _t, user, org_id = await _org(client, db_session)
    await _add_usage(db_session, user, org_id, call_seconds=120, message_ms=30_000)
    last_month = month_start() - dt.timedelta(days=3)
    await _add_usage(db_session, user, org_id, call_seconds=6000, when=last_month)
    assert await voice_minutes_used(db_session, org_id) == 2.5


async def test_usage_is_per_organization(client, db_session):
    _t, user, org_a = await _org(client, db_session, "voice-a@example.com")
    _t2, user_b, org_b = await _org(client, db_session, "voice-b@example.com")
    await _add_usage(db_session, user, org_a, call_seconds=600)
    assert await voice_minutes_used(db_session, org_b) == 0


async def test_summary_reports_limit_and_remaining(client, db_session):
    _t, user, org_id = await _org(client, db_session, "voice-summary@example.com")
    await _add_usage(db_session, user, org_id, call_seconds=300)
    summary = await voice_usage_summary(db_session, org_id, {"voice_minutes_per_month": 20})
    assert summary["used_minutes"] == 5 and summary["limit_minutes"] == 20 and summary["remaining_minutes"] == 15
    unlimited = await voice_usage_summary(db_session, org_id, {})
    assert unlimited["limit_minutes"] is None and unlimited["remaining_minutes"] is None


async def test_the_limit_blocks_once_reached(client, db_session):
    _t, user, org_id = await _org(client, db_session, "voice-limit@example.com")
    await _add_usage(db_session, user, org_id, call_seconds=600)
    await assert_voice_minutes_available(db_session, org_id, {"voice_minutes_per_month": 11})
    await assert_voice_minutes_available(db_session, org_id, {})
    with pytest.raises(HTTPException) as exc:
        await assert_voice_minutes_available(db_session, org_id, {"voice_minutes_per_month": 10})
    assert exc.value.status_code == 429


async def test_outbound_calls_are_refused_when_the_monthly_minutes_are_used_up(client, db_session):
    token, user, org_id = await _org(client, db_session, "voice-outbound@example.com")
    await _add_usage(db_session, user, org_id, call_seconds=600)
    r = await client.patch(f"/organizations/{org_id}/settings", json={"voice_minutes_per_month": 5}, headers=_h(token))
    assert r.status_code == 200 and r.json()["voice_minutes_per_month"] == 5
    blocked = await client.post(f"/organizations/{org_id}/twilio/outbound", json={"to": "+15551234567", "agent_id": str(uuid.uuid4())}, headers=_h(token))
    assert blocked.status_code == 429


async def test_usage_endpoint(client, db_session):
    token, user, org_id = await _org(client, db_session, "voice-endpoint@example.com")
    await _add_usage(db_session, user, org_id, call_seconds=90)
    await client.patch(f"/organizations/{org_id}/settings", json={"voice_minutes_per_month": 10}, headers=_h(token))
    body = (await client.get(f"/organizations/{org_id}/usage/voice-minutes", headers=_h(token))).json()
    assert body["used_minutes"] == 1.5 and body["limit_minutes"] == 10 and body["remaining_minutes"] == 8.5
