"""add responses and citations tables (Partie 6.1.1-6.1.10)

Revision ID: 0066
Revises: 0065
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0066"
down_revision: Union[str, None] = "0065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("confidence_factors", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_responses_organization_id", "responses", ["organization_id"])
    op.execute("ALTER TABLE public.responses ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "citations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("response_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_title", sa.String(length=500), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("citation_number", sa.Integer(), nullable=False),
        sa.Column("position_start", sa.Integer(), nullable=True),
        sa.Column("position_end", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("document_name", sa.String(length=500), nullable=True),
        sa.Column("document_type", sa.String(length=127), nullable=True),
        sa.Column("source_section", sa.String(length=500), nullable=True),
        sa.Column("source_heading", sa.String(length=500), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("relevance_label", sa.String(length=10), nullable=True),
        sa.Column("text_preview", sa.String(length=500), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["response_id"], ["responses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_citations_response_id", "citations", ["response_id"])
    op.create_index("ix_citations_document_id", "citations", ["document_id"])
    op.execute("ALTER TABLE public.citations ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.citations DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_citations_document_id", table_name="citations")
    op.drop_index("ix_citations_response_id", table_name="citations")
    op.drop_table("citations")

    op.execute("ALTER TABLE public.responses DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_responses_organization_id", table_name="responses")
    op.drop_table("responses")
