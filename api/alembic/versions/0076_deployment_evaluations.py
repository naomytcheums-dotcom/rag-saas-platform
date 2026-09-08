"""add deployment_evaluations (Partie 7.3.8)

Revision ID: 0076
Revises: 0075
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0076"
down_revision: Union[str, None] = "0075"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deployment_evaluations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evaluation_job_id", sa.Uuid(), sa.ForeignKey("evaluation_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_deployment_evaluations_agent_id", "deployment_evaluations", ["agent_id"])


def downgrade() -> None:
    op.drop_table("deployment_evaluations")
