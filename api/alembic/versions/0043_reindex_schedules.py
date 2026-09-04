"""add reindex_schedules table and documents.reindex_schedule (Partie 2.2.15)

Revision ID: 0043
Revises: 0042
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No RLS statement needed for this column -- documents already
    # carries RLS since migration 0002.
    op.add_column("documents", sa.Column("reindex_schedule", sa.String(length=100), nullable=True))

    op.create_table(
        "reindex_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_name", sa.String(length=200), nullable=False),
        sa.Column("cron_pattern", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reindex_schedules_organization_id", "reindex_schedules", ["organization_id"])
    # Real, deliberate, inline from the start -- see migration 0042's
    # own equivalent comment; this codebase has forgotten this twice
    # before (0031, then 0034/0035) and is not forgetting a third time.
    op.execute("ALTER TABLE public.reindex_schedules ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.reindex_schedules DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_reindex_schedules_organization_id", table_name="reindex_schedules")
    op.drop_table("reindex_schedules")
    op.drop_column("documents", "reindex_schedule")
