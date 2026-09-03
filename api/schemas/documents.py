"""Request/response bodies for api/routers/documents.py (Partie
2.1.1/2.1.10). Deliberately has NO field for `file_key` -- that's an
internal S3 storage detail, not something a client needs or should be
able to see."""

import datetime as dt
import uuid

from pydantic import BaseModel, HttpUrl


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
    # None for every file upload -- only real for a document imported
    # via Partie 2.1.10's POST .../documents/url (see
    # api/models/document.py's own docstring on this column).
    source_url: str | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
    processed_at: dt.datetime | None


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]


class DocumentUrlImportRequest(BaseModel):
    """Partie 2.1.10, item 1's own request body. `HttpUrl` gives a
    real, free first layer of validation (rejects a non-http(s) scheme
    or a structurally invalid URL with a clean 422 before this request
    even reaches api/security/documents.py's own import_document_from_url)
    -- confirmed for real, it does NOT reject embedded credentials
    (`http://user:pass@host/`), which is why validate_url below still
    has its own real check for that, not a redundant one."""

    url: HttpUrl
