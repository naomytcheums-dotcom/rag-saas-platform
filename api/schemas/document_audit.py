"""Response body for the Partie 2.2.10 history route in
api/routers/documents.py."""

import datetime as dt
import uuid

from pydantic import BaseModel


class DocumentAuditLogResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    action: str
    user_id: uuid.UUID | None
    changes: dict | None
    metadata: dict | None
    timestamp: dt.datetime
