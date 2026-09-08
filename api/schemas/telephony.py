"""Response body for Partie 8.2.13's own real call-history listing."""

import datetime as dt
import uuid

from pydantic import BaseModel


class CallRecordResponse(BaseModel):
    id: uuid.UUID
    call_sid: str
    conversation_id: uuid.UUID | None
    agent_id: uuid.UUID | None
    from_number: str
    to_number: str
    status: str
    duration_seconds: int | None
    recording_url: str | None
    transcription: str | None
    started_at: dt.datetime
    ended_at: dt.datetime | None

    model_config = {"from_attributes": True}
