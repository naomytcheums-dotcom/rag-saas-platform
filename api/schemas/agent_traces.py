"""Request/response bodies for api/routers/agent_traces.py (Partie 5.1.14)."""

import datetime as dt
import uuid

from pydantic import BaseModel


class AgentTraceResponse(BaseModel):
    id: uuid.UUID
    agent_run_id: uuid.UUID
    step_number: int
    step_type: str
    description: str
    input: dict | None
    output: dict | None
    duration_ms: int | None
    status: str
    error: str | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}
