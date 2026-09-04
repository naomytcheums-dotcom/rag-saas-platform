"""add document_keywords and document_entities tables (Partie 3.1.10)

Revision ID: 0046
Revises: 0045
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: Union[str, None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_keywords",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("keyword", sa.String(length=200), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_keywords_document_id", "document_keywords", ["document_id"])
    op.execute("ALTER TABLE public.document_keywords ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "document_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_value", sa.String(length=500), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_entities_document_id", "document_entities", ["document_id"])
    op.execute("ALTER TABLE public.document_entities ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.document_entities DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_document_entities_document_id", table_name="document_entities")
    op.drop_table("document_entities")
    op.execute("ALTER TABLE public.document_keywords DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_document_keywords_document_id", table_name="document_keywords")
    op.drop_table("document_keywords")
