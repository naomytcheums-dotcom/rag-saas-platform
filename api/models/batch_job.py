"""
Partie 2.2.16 -- a generic, per-item-tracked batch job wrapping 5 real,
already-existing, unchanged operations (upload/reindex/delete/sync/
replace), each already built and tested by an earlier Partie 2.2
étape. `BatchJob` is NOT a second, competing batch-upload mechanism --
Partie 2.2.1's own `process_upload_batch` (one HTTP multipart request,
aggregate-only result) still exists unchanged for that specific real
scenario; THIS étape's own real, distinct value is per-item, PERSISTED
progress tracking, resumability, and cancellation across ANY of the 5
supported real operations, not just uploads.
"""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class BatchJobType(StrEnum):
    upload = "upload"
    reindex = "reindex"
    delete = "delete"
    sync = "sync"
    replace = "replace"


class BatchJobStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    # Not one of this étape's own literal 4 values -- a real, small,
    # deliberate addition: item 5's own literal `cancel_batch_job`
    # function needs a real, honest terminal state to land a cancelled
    # job in, distinct from `failed` (a cancellation is a deliberate
    # choice, not an error) -- the same "a name existing for what a
    # literally-requested function actually needs to produce" reasoning
    # as Partie 2.2.10's own `restored` action.
    cancelled = "cancelled"


class BatchJobItemStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=BatchJobStatus.pending.value)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Real, per-item INPUT data lives here, under `config["items"]` --
    # a real, necessary, DOCUMENTED addition beyond this étape's own
    # literal "configuration du job" description: `process_batch_job`
    # runs later, in a separate real Celery task/DB session, and needs
    # a real, durable place to read each item's own real input from
    # (e.g. an upload's own real file bytes, base64-encoded -- the SAME
    # real, documented exception to "never smuggle a blob through" this
    # codebase already made once, for the SAME reason, in Partie
    # 2.2.1's own schedule_upload_batch_processing) -- there is nowhere
    # else durable for it to live between job creation and processing.
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_batch_jobs_organization_id", "organization_id"),
    )


class BatchJobItem(Base):
    __tablename__ = "batch_job_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batch_jobs.id", ondelete="CASCADE"), nullable=False)
    # Not one of this étape's own literal columns -- a real, small,
    # necessary addition: this table's own literal columns have no
    # ordering field at all, but `process_batch_job` must align each
    # real row back to its own real input at `BatchJob.config["items"][sequence]`
    # -- `id`'s own real insertion order is not something this
    # codebase relies on elsewhere for correctness, so a real, explicit
    # column is the honest choice instead.
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    # Nullable -- the real target this item ends up affecting
    # (a document id for reindex/delete/replace, the newly real created
    # document's own id for upload, a source id for sync) is often only
    # known once processing actually reaches this item, matching this
    # étape's own literal "item_id nullable" wording.
    item_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=BatchJobItemStatus.pending.value)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_batch_job_items_batch_job_id", "batch_job_id"),
    )
