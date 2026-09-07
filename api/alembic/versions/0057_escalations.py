"""add escalations table (Partie 5.2.9)

Revision ID: 0057
Revises: 0056
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0057"
down_revision: Union[str, None] = "0056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "escalations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("issue", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("priority", sa.String(length=10), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="open"),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_escalations_organization_id", "escalations", ["organization_id"])
    op.create_index("ix_escalations_status", "escalations", ["status"])
    op.execute("ALTER TABLE public.escalations ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.escalations DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_escalations_status", table_name="escalations")
    op.drop_index("ix_escalations_organization_id", table_name="escalations")
    op.drop_table("escalations")
