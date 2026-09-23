"""Phase 5, Étape 11 -- response body for
GET /workflows/runs/{run_id}/trace."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class WorkflowNodeExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_run_id: uuid.UUID
    step_number: int
    node_id: str
    node_type: str
    input: dict | None
    output: dict | None
    duration_ms: int | None
    status: str
    error: str | None
    created_at: dt.datetime
