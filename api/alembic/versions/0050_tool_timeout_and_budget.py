"""add tool_timeout_overrides and tool_budgets tables (Partie 5.1.4/5.1.5)

Revision ID: 0050
Revises: 0049
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0050"
down_revision: Union[str, None] = "0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_timeout_overrides",
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("tool_name"),
    )
    op.execute("ALTER TABLE public.tool_timeout_overrides ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "tool_budgets",
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("budget_limit", sa.Integer(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("tool_name"),
    )
    op.execute("ALTER TABLE public.tool_budgets ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.tool_budgets DISABLE ROW LEVEL SECURITY")
    op.drop_table("tool_budgets")
    op.execute("ALTER TABLE public.tool_timeout_overrides DISABLE ROW LEVEL SECURITY")
    op.drop_table("tool_timeout_overrides")
