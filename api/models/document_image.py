"""Partie 3.1.5 -- one real, embedded image extracted from a document
(PDF/DOCX/EPUB -- see api/services/image_extraction.py's own docstring
for HTML's own real, different, deliberately narrower scope), stored
in S3 alongside the document itself."""

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class DocumentImage(Base):
    __tablename__ = "document_images"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    file_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    # Nullable -- a real image whose own bytes Pillow cannot decode
    # (a genuinely corrupt or unusual embedded format) still gets
    # stored for real (the raw bytes are real regardless), just
    # without real width/height/format metadata -- an honest `None`,
    # never a fabricated dimension.
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Named `metadata_json`, not `metadata` -- collides with
    # SQLAlchemy's own Base.metadata, same reasoning as every other
    # such column in this codebase (Document.metadata_json, etc.).
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_document_images_document_id", "document_id"),
    )
