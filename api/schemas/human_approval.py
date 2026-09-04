"""Request/response bodies for api/routers/human_approval.py (Partie 5.1.10)."""

import datetime as dt
import uuid

from pydantic import BaseModel


class HumanApprovalResponse(BaseModel):
    id: uuid.UUID
    agent_run_id: uuid.UUID
    tool_name: str
    params: dict
    status: str
    requested_by: uuid.UUID | None
    approved_by: uuid.UUID | None
    requested_at: dt.datetime
    approved_at: dt.datetime | None
    expires_at: dt.datetime
    comment: str | None

    model_config = {"from_attributes": True}


class HumanApprovalDecisionRequest(BaseModel):
    comment: str | None = None
