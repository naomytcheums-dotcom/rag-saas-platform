"""add agent_runs table (fix to Partie 5.1.1 -- persistent, shared agent run registry)

Revision ID: 0048
Revises: 0047
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0048"
down_revision: Union[str, None] = "0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.String(length=200), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("stop_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_agent_id", "agent_runs", ["agent_id"])
    op.create_index("ix_agent_runs_organization_id", "agent_runs", ["organization_id"])
    op.execute("ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.agent_runs DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_agent_runs_organization_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_id", table_name="agent_runs")
    op.drop_table("agent_runs")
