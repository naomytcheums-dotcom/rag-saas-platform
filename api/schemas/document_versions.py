"""Request/response bodies for the Partie 2.2.7 version routes in
api/routers/documents.py."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class DocumentVersionRestoreRequest(BaseModel):
    """Item 4's own literal `POST .../versions/restore` request body."""

    version_number: int = Field(ge=1)


class DocumentVersionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    file_size: int
    metadata: dict | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
