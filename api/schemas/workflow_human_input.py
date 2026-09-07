"""Request/response bodies for the Partie 5.4.9 human-block endpoints."""

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class WorkflowHumanInputResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_run_id: uuid.UUID
    node_id: str
    message: str
    input_type: str
    options: list | None
    required: bool
    status: str
    value: Any
    submitted_by: uuid.UUID | None
    submitted_at: dt.datetime | None
    created_at: dt.datetime
    expires_at: dt.datetime | None


class WorkflowHumanInputSubmitRequest(BaseModel):
    value: Any
