"""add tool_fallbacks and llm_fallbacks tables (Partie 5.1.7)

Revision ID: 0051
Revises: 0050
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_fallbacks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("fallback_tool", sa.String(length=200), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tool_name", "priority", name="uq_tool_fallbacks_tool_priority"),
    )
    op.create_index("ix_tool_fallbacks_tool_name", "tool_fallbacks", ["tool_name"])
    op.execute("ALTER TABLE public.tool_fallbacks ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "llm_fallbacks",
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("fallback_provider", sa.String(length=50), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("provider"),
    )
    op.execute("ALTER TABLE public.llm_fallbacks ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.llm_fallbacks DISABLE ROW LEVEL SECURITY")
    op.drop_table("llm_fallbacks")
    op.execute("ALTER TABLE public.tool_fallbacks DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_tool_fallbacks_tool_name", table_name="tool_fallbacks")
    op.drop_table("tool_fallbacks")
