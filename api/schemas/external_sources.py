"""Request/response bodies for api/routers/external_sources.py (Partie
2.2.14). Deliberately no `config` field ever appears in a RESPONSE --
see api/models/external_source.py's own docstring on why the whole
blob is treated as sensitive by default; a caller that set it can
still update it (write-only), but never reads a real credential back
out over the API."""

import datetime as dt
import uuid

from pydantic import BaseModel


class ExternalSourceCreateRequest(BaseModel):
    source_type: str
    source_id: str
    workspace_id: uuid.UUID | None = None
    config: dict | None = None
    enabled: bool = True


class ExternalSourceUpdateRequest(BaseModel):
    source_id: str | None = None
    config: dict | None = None
    enabled: bool | None = None


class ExternalSourceResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    workspace_id: uuid.UUID | None
    source_type: str
    source_id: str
    enabled: bool
    last_sync_at: dt.datetime | None
    sync_status: str
    sync_error: str | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


class ExternalSourceSyncResponse(BaseModel):
    source_id: uuid.UUID
    sync_status: str


class ExternalSourceSyncAllResponse(BaseModel):
    total: int
    synced: int
    failed: int
