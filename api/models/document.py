"""
Partie 2.1.1/2.1.10 -- documents an organization imports into its
knowledge base, and the chunks each one is split into for retrieval.

`status` is a plain String, not a native Postgres enum -- same
reasoning as AuditLog.action / CustomDomainStatus: a fixed, app-level
StrEnum (DocumentStatus below) that never needs a migration to extend.

Both `metadata_json` columns are named that way, not `metadata` --
that name collides with SQLAlchemy's own Base.metadata attribute on
every declarative model (same reasoning as AuditLog.metadata_json /
OrganizationUsageDetail.metadata_json). Generic sa.JSON, not
postgresql.JSONB, for the same cross-dialect reason those two use --
the SQLite fast suite (schema built straight from these ORM models via
Base.metadata.create_all(), never Alembic) cannot represent JSONB.

`DocumentChunk.embedding` is ALSO generic sa.JSON (a plain list of
floats), not pgvector's native VECTOR type -- a deliberate choice, not
an oversight: pgvector's SQLAlchemy type has no SQLite equivalent at
all (unlike JSON, which degrades to JSONB on Postgres and TEXT on
SQLite transparently), so using it here would make this table
altogether unrepresentable in the fast suite. A real pgvector column
with an ANN index is genuine future work once retrieval actually needs
efficient similarity search at scale (Partie 3/4's own scope) -- for
2.1.1 (import + chunking), a Python-side list of floats is real,
correct, and keeps this table testable the same way every other table
in this codebase is.
"""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class DocumentStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    # Nullable: a document can belong to the organization at large, not
    # every workspace needs one -- same optionality as
    # api/models/custom_domain.py's own org-level-by-default shape.
    # SET NULL, not CASCADE: deleting a workspace should not delete the
    # documents filed under it, only un-file them (same reasoning as
    # Workspace.created_by).
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    # Nullable -- only set for a document imported via Partie 2.1.10's
    # POST .../documents/url (api/security/documents.py's
    # import_document_from_url), NULL for every file upload. Real
    # provenance a file upload has no equivalent of (a filename isn't
    # "where this came from" the way a URL genuinely is).
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    file_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(127), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=DocumentStatus.pending.value)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Nullable, SET NULL on delete: a document outlives whoever
    # uploaded it -- it's organization property, not personal property
    # of its uploader (same reasoning as Workspace.created_by).
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # The only read patterns this table serves (list_documents,
        # get_document) are always "this org's rows" or "one document
        # by id" -- organization_id is what every list query filters
        # on, the same access pattern as api/models/custom_domain.py's
        # own index.
        Index("ix_documents_organization_id", "organization_id"),
        Index("ix_documents_workspace_id", "workspace_id"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # See this module's own docstring for why this is a plain JSON list
    # of floats, not pgvector's native VECTOR type. Nullable: a chunk
    # exists (real content, real metadata) the moment it's created by
    # chunking -- embedding generation is a separate step of
    # process_pdf_document that can legitimately fail (or simply not
    # have run yet) without the chunk itself being invalid.
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_document_chunks_document_id", "document_id"),
    )
