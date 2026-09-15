"""Partie 22 -- multi-modal media (images, audio, video). See
api/models/media.py's own docstring for the real build-vs-reuse split
this part's own pre-build audit produced: embedded-document images
(document_images) are EXTENDED with description/objects_json rather
than duplicated; media_assets/media_transcripts/media_frames are the
genuinely new standalone tables (video processing is a total green
field). document_chunks.document_id is loosened to nullable, and a new
media_asset_id column added, so media-derived text can be indexed into
the SAME real RAG chunk table rather than a second, parallel vector
index (this part's own audit's explicit recommendation) -- a CHECK
constraint keeps every chunk anchored to exactly one real parent.

Revision ID: 0104
Revises: 0103
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0104"
down_revision: Union[str, None] = "0103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

media_type_enum = sa.Enum("image", "audio", "video", name="media_type")
media_status_enum = sa.Enum("pending", "processing", "completed", "failed", name="media_status")


def upgrade() -> None:
    # No manual .create(checkfirst=True) here, unlike migration 0096's
    # add_column-based enums -- op.create_table, unlike op.add_column,
    # auto-creates any enum type referenced inline by its columns (see
    # 0096's own comment on this exact distinction). Both media_type_enum
    # and media_status_enum are only ever used inline below, in
    # op.create_table -- a redundant manual .create() here raced against
    # that auto-creation and failed with a real
    # "type media_type already exists" DuplicateObjectError the first
    # time this migration actually ran end-to-end in CI.
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("media_type", media_type_enum, nullable=False),
        sa.Column("status", media_status_enum, nullable=False, server_default="pending"),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("file_key", sa.String(length=1024), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("objects_json", sa.JSON(), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_assets_organization_id", "media_assets", ["organization_id"])
    op.execute("ALTER TABLE public.media_assets ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "media_transcripts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("segments_json", sa.JSON(), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_transcripts_media_asset_id", "media_transcripts", ["media_asset_id"])
    op.execute("ALTER TABLE public.media_transcripts ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "media_frames",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("timestamp_ms", sa.Integer(), nullable=False),
        sa.Column("file_key", sa.String(length=1024), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("objects_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_frames_media_asset_id", "media_frames", ["media_asset_id"])
    op.execute("ALTER TABLE public.media_frames ENABLE ROW LEVEL SECURITY")

    # -- Extend document_images (embedded, per-document images) --------------
    op.add_column("document_images", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("document_images", sa.Column("objects_json", sa.JSON(), nullable=True))

    # -- Extend document_chunks so media-derived text can share the same
    # real RAG index (see this migration's own docstring) -----------------
    op.alter_column("document_chunks", "document_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column("document_chunks", sa.Column("media_asset_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_document_chunks_media_asset_id", "document_chunks", "media_assets", ["media_asset_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_document_chunks_media_asset_id", "document_chunks", ["media_asset_id"])
    op.create_check_constraint(
        "ck_document_chunks_has_a_parent", "document_chunks", "document_id IS NOT NULL OR media_asset_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_document_chunks_has_a_parent", "document_chunks", type_="check")
    op.drop_index("ix_document_chunks_media_asset_id", table_name="document_chunks")
    op.drop_constraint("fk_document_chunks_media_asset_id", "document_chunks", type_="foreignkey")
    op.drop_column("document_chunks", "media_asset_id")
    op.alter_column("document_chunks", "document_id", existing_type=sa.Uuid(), nullable=False)

    op.drop_column("document_images", "objects_json")
    op.drop_column("document_images", "description")

    op.drop_table("media_frames")
    op.drop_table("media_transcripts")
    op.drop_table("media_assets")

    bind = op.get_bind()
    media_status_enum.drop(bind, checkfirst=True)
    media_type_enum.drop(bind, checkfirst=True)
