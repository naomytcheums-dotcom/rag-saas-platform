"""
Partie 2.2.14 -- a persistent, recurring connection to an external
CONTAINER (a GitHub repo, a Google Drive folder, a Notion database, a
Confluence space, a OneDrive folder) that this organization wants kept
in sync automatically, rather than imported once via the existing
Partie 2.1.12-2.1.18 routes.

`config_encrypted` is a real, deliberate, DOCUMENTED deviation from
this étape's own literal "config (JSONB)" column: an opaque,
Fernet-encrypted JSON blob (api/security/secret_encryption.py, the
SAME shared encryption-at-rest this codebase already uses for JWT
signing keys and enterprise SSO client secrets) stored as TEXT, not
raw, queryable JSONB. Every real source type this étape's own literal
list names authenticates via a token/refresh-token this codebase
already treats as a real secret (see api/security/documents.py's own
GITHUB_API_TOKEN/GOOGLE_DRIVE_REFRESH_TOKEN/NOTION_API_TOKEN/
CONFLUENCE_API_TOKEN/ONEDRIVE_REFRESH_TOKEN) -- treating the WHOLE
config blob as sensitive by default is safer than trusting every
future caller to remember which individual sub-key needs encrypting.
"""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class ExternalSourceType(StrEnum):
    """This étape's own literal, fixed list of 5 supported source
    types -- a plain app-level StrEnum, not a native Postgres enum,
    same reasoning as api/models/document.py's own DocumentStatus
    (never needs a migration to extend)."""

    github = "github"
    google_drive = "google_drive"
    notion = "notion"
    confluence = "confluence"
    onedrive = "onedrive"


class ExternalSourceSyncStatus(StrEnum):
    idle = "idle"
    syncing = "syncing"
    failed = "failed"


class ExternalSource(Base):
    __tablename__ = "external_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    # Nullable, SET NULL -- same optionality/deletion reasoning as
    # api/models/document.py's own workspace_id: a source belongs to
    # the organization at large by default, and outlives a workspace
    # deleted out from under it (only un-files it, imported documents
    # keep their own real workspace_id independently).
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # The real, source-specific container identifier this étape's own
    # literal docstring names ("dossier Drive, base Notion, etc.") --
    # a GitHub repo URL, a Drive folder id, a Notion database id, a
    # Confluence space key, or a OneDrive folder id, depending on
    # `source_type` -- see api/security/external_sources.py's own
    # sync_external_source for exactly how each is used.
    source_id: Mapped[str] = mapped_column(String(2048), nullable=False)
    config_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False, default=ExternalSourceSyncStatus.idle.value)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Not one of this étape's own literal columns -- a real, small,
    # deliberate addition (the SAME "small, optional, documented
    # extension" pattern as Partie 2.2.10's own triggered_by): every
    # document a sync creates needs a real `created_by` to pass through
    # to the SAME existing import pipelines Partie 2.1.12-2.1.18 already
    # built (see sync_external_source's own docstring) -- the real
    # human who configured this source is the honest, natural actor to
    # attribute those to, not a fabricated one.
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # The only real read pattern this table serves -- "this org's
        # own sources" -- same access pattern as api/models/document.py's
        # own organization_id index.
        Index("ix_external_sources_organization_id", "organization_id"),
    )
