"""add human_approvals table (Partie 5.1.10)

Revision ID: 0052
Revises: 0051
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "human_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_human_approvals_organization_id", "human_approvals", ["organization_id"])
    op.create_index("ix_human_approvals_agent_run_id", "human_approvals", ["agent_run_id"])
    op.execute("ALTER TABLE public.human_approvals ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.human_approvals DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_human_approvals_agent_run_id", table_name="human_approvals")
    op.drop_index("ix_human_approvals_organization_id", table_name="human_approvals")
    op.drop_table("human_approvals")
