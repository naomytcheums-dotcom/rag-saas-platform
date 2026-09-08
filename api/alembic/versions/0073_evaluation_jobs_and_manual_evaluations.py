"""add evaluation_jobs, manual_evaluations, evaluation_results.evaluation_job_id (Partie 7.3.1/7.3.2)

Revision ID: 0073
Revises: 0072
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0073"
down_revision: Union[str, None] = "0072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_set_id", sa.Uuid(), sa.ForeignKey("question_sets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("model_config_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("completed_questions", sa.Integer(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_evaluation_jobs_dataset_id", "evaluation_jobs", ["dataset_id"])

    op.add_column(
        "evaluation_results",
        sa.Column("evaluation_job_id", sa.Uuid(), sa.ForeignKey("evaluation_jobs.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_evaluation_results_evaluation_job_id", "evaluation_results", ["evaluation_job_id"])

    op.create_table(
        "manual_evaluations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evaluator_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("criteria", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_manual_evaluations_question_id", "manual_evaluations", ["question_id"])
    op.create_index("ix_manual_evaluations_evaluator_id", "manual_evaluations", ["evaluator_id"])


def downgrade() -> None:
    op.drop_table("manual_evaluations")
    op.drop_index("ix_evaluation_results_evaluation_job_id", "evaluation_results")
    op.drop_column("evaluation_results", "evaluation_job_id")
    op.drop_table("evaluation_jobs")
