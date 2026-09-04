"""add document_audit_logs table (Partie 2.2.10)

Revision ID: 0038
Revises: 0037
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_audit_logs_document_id", "document_audit_logs", ["document_id"])
    # Real, deliberate, inline this time -- every application table has
    # needed this since migration 0002, and TWO prior migrations in
    # this exact codebase (0031/0032, then 0034+0035/0037) already
    # forgot it once before catching it via CI. Not forgetting it a
    # third time.
    op.execute("ALTER TABLE public.document_audit_logs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.document_audit_logs DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_document_audit_logs_document_id", table_name="document_audit_logs")
    op.drop_table("document_audit_logs")
