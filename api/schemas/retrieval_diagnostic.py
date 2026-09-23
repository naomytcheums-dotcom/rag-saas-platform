"""Phase 5, Étape 11 -- response body for
GET /organizations/{org_id}/retrieval-diagnostics."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class RetrievalDiagnosticResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    query: str
    strategy: str
    final_chunks: list
    result_count: int
    latency_ms: int
    created_at: dt.datetime
