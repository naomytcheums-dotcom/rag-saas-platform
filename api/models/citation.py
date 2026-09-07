"""
Partie 6.1.1 -- the real `Citation` entity: one real, structured
source reference attached to one real `Response`.

**All columns from Partie 6.1.1 through 6.1.9 declared together, in
one real migration** -- the same "declare the whole real entity once,
wire each étape's own real functions in its own later commit"
approach already used throughout Parties 5.3/5.4 (`Agent`, `Workflow`).
`document_name`/`document_type` (6.1.2), `source_section`/
`source_heading` (6.1.3), `chunk_index` (6.1.5), `relevance_label`
(6.1.6), `text_preview` (6.1.7), `is_primary` (6.1.9) are real, but
inert until their own étape's real functions consume them.

**Robustesse (vision critique) -- what happens if the source is
deleted**: `document_id`/`chunk_id` are real FKs with `ondelete="SET
NULL"`, deliberately NOT `CASCADE` -- a real citation is a historical
record of what a real response actually cited AT GENERATION TIME; a
document or chunk being deleted later must never silently delete the
citation that already quoted it. `document_name`/`source_title`/
`text` are real, DENORMALIZED copies captured at citation time for
exactly this reason -- they remain real and readable even after
`document_id`/`chunk_id` go `NULL`."""

import datetime as dt
import uuid

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    response_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("responses.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    citation_number: Mapped[int] = mapped_column(Integer, nullable=False)
    position_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Partie 6.1.2 -- real, denormalized (survives a real document
    # deletion, see this module's own top docstring).
    document_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(127), nullable=True)
    # Partie 6.1.3 -- real, extracted from the chunk's own real
    # metadata_json ("heading"/"level" for Markdown -- see
    # api/services/document_extraction.py's own real per-format shape).
    source_section: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_heading: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Partie 6.1.5 -- real, 1-based, straight from DocumentChunk's own
    # real, persisted chunk_index column (migration 0068) -- see
    # api/services/citation_chunk.py's own docstring for why this is a
    # real column rather than a derived approximation.
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Partie 6.1.6 -- "high"/"medium"/"low", real, computed from
    # relevance_score against RELEVANCE_THRESHOLD_HIGH/MEDIUM.
    relevance_label: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Partie 6.1.7 -- a real, short preview of `text` for compact UIs.
    text_preview: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Partie 6.1.9 -- real primary/secondary split (top N vs. the rest,
    # above CITATION_SECONDARY_THRESHOLD).
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
