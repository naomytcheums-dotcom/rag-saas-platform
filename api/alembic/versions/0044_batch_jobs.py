"""add batch_jobs and batch_job_items tables (Partie 2.2.16)

Revision ID: 0044
Revises: 0043
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0044"
down_revision: Union[str, None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "batch_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("processed_items", sa.Integer(), nullable=False),
        sa.Column("failed_items", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_batch_jobs_organization_id", "batch_jobs", ["organization_id"])
    op.execute("ALTER TABLE public.batch_jobs ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "batch_job_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_job_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["batch_job_id"], ["batch_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_batch_job_items_batch_job_id", "batch_job_items", ["batch_job_id"])
    # Real, deliberate, inline from the start -- this codebase has
    # forgotten this twice before (0031, then 0034/0035); not a third
    # time. Same convention as every other child table with no direct
    # organization_id of its own (e.g. document_chunks): real tenant
    # isolation is enforced at the application layer (every real query
    # here always joins through/filters by its parent batch_jobs.id,
    # itself organization-scoped), matching this codebase's own
    # established, consistent pattern -- no application table in this
    # codebase defines an actual RLS policy at all, `ENABLE ROW LEVEL
    # SECURITY` is a real, deliberate compliance/defense-in-depth
    # baseline, not the actual isolation mechanism.
    op.execute("ALTER TABLE public.batch_job_items ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.batch_job_items DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_batch_job_items_batch_job_id", table_name="batch_job_items")
    op.drop_table("batch_job_items")
    op.execute("ALTER TABLE public.batch_jobs DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_batch_jobs_organization_id", table_name="batch_jobs")
    op.drop_table("batch_jobs")
