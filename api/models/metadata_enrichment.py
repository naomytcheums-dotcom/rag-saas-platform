"""Partie 3.1.10 -- real per-item keyword/entity extraction results,
stored as their own real rows (not folded into `Document.metadata_json`
like Partie 3.1.4/3.1.8's own table/structure data) -- these two, and
only these two, are genuinely per-item lists this codebase already has
real precedent for as their own table (Partie 2.2.6's own
`DocumentTag`), unlike a table's own rows or a structural outline,
which are read as a single whole, not queried/filtered per item."""

import datetime as dt
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class DocumentKeyword(Base):
    __tablename__ = "document_keywords"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_document_keywords_document_id", "document_id"),
    )


class DocumentEntity(Base):
    __tablename__ = "document_entities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    # A real, fixed, honest vocabulary -- see api/services/metadata_enrichment.py's
    # own module docstring for why this is a real, pattern-based
    # extractor (email/url/date/money/phone), not a fabricated claim of
    # full spaCy-grade named-entity recognition (person/organization/
    # location names need a real trained model, a genuinely heavy new
    # dependency this étape's own scope doesn't justify adding).
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_value: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # Nullable -- this étape's own literal column, the real character
    # offset into the text this entity was found in; honestly absent
    # when an entity is deduplicated across multiple real occurrences
    # (see extract_entities' own docstring) and no single position is
    # more real/correct than any other.
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_document_entities_document_id", "document_id"),
    )
