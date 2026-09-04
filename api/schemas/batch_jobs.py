"""Request/response bodies for api/routers/batch_jobs.py (Partie
2.2.16). `items`/`config` are deliberately plain `dict`/`list[dict]` --
each real `job_type`'s own item shape differs (an upload needs
filename/content/content_type, a delete needs only a document_id) --
a strict per-type schema would be real, disproportionate complexity for
this étape's own scope; a malformed item surfaces as THAT item's own
real, recorded failure at processing time instead (see
api/security/batch_jobs.py's own process_batch_job)."""

import datetime as dt
import uuid

from pydantic import BaseModel


class BatchJobCreateRequest(BaseModel):
    job_type: str
    items: list[dict]
    config: dict | None = None


class BatchJobResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    job_type: str
    status: str
    total_items: int
    processed_items: int
    failed_items: int
    created_by: uuid.UUID | None
    created_at: dt.datetime
    started_at: dt.datetime | None
    completed_at: dt.datetime | None
    error: str | None


class BatchJobItemResponse(BaseModel):
    id: uuid.UUID
    batch_job_id: uuid.UUID
    sequence: int
    item_id: uuid.UUID | None
    status: str
    error: str | None
    processed_at: dt.datetime | None
