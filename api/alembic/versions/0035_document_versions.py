"""add document_versions table and documents.current_version_id (Partie 2.2.7)

Revision ID: 0035
Revises: 0034
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # document_versions.document_id references the ALREADY-existing
    # documents table (migration 0031) -- created first, before
    # documents.current_version_id's own FK back to THIS table can be
    # added, since the two tables reference each other (a real,
    # necessary two-step sequence, not a circular DDL statement).
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("file_key", sa.String(length=1024), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_versions_document_id_version_number"),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])

    op.add_column("documents", sa.Column("current_version_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_documents_current_version_id_document_versions", "documents", "document_versions",
        ["current_version_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_documents_current_version_id_document_versions", "documents", type_="foreignkey")
    op.drop_column("documents", "current_version_id")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")
