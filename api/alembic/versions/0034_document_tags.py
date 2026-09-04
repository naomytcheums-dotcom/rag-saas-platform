"""add document_tags and document_tag_assignments tables (Partie 2.2.6)

Revision ID: 0034
Revises: 0033
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_document_tags_organization_id_name"),
    )
    op.create_index("ix_document_tags_organization_id", "document_tags", ["organization_id"])

    op.create_table(
        "document_tag_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["document_tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "tag_id", name="uq_document_tag_assignments_document_id_tag_id"),
    )
    op.create_index("ix_document_tag_assignments_document_id", "document_tag_assignments", ["document_id"])
    op.create_index("ix_document_tag_assignments_tag_id", "document_tag_assignments", ["tag_id"])


def downgrade() -> None:
    op.drop_index("ix_document_tag_assignments_tag_id", table_name="document_tag_assignments")
    op.drop_index("ix_document_tag_assignments_document_id", table_name="document_tag_assignments")
    op.drop_table("document_tag_assignments")
    op.drop_index("ix_document_tags_organization_id", table_name="document_tags")
    op.drop_table("document_tags")
