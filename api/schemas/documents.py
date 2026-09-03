"""Request/response bodies for api/routers/documents.py (Partie 2.1.1).
Deliberately has NO field for `file_key` -- that's an internal S3
storage detail, not something a client needs or should be able to see."""

import datetime as dt
import uuid

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    workspace_id: uuid.UUID | None
    name: str
    file_size: int
    file_type: str
    status: str
    # Exposed as `metadata` in the API (matching this step's own literal
    # field name) even though the ORM attribute is metadata_json -- see
    # api/models/document.py's own docstring for why the ORM attribute
    # itself can't be named `metadata` (collides with SQLAlchemy's
    # Base.metadata).
    metadata: dict | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
    processed_at: dt.datetime | None


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
