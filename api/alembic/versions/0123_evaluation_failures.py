"""Phase 5, Étape 14 -- real, additive table: `evaluation_failures`,
closing the gap Étape 10 traced ("analyse d'échecs Eval Lab") --
before this, a question that raised inside `run_evaluation_job` was
only ever logged (WARNING), never persisted; a failure-analysis UI has
nothing real to show without an underlying row per failure. See
api/models/evaluation.py's EvaluationFailure docstring for the full
reasoning, including why "hallucination" is deliberately NOT a stored
category here (computed at read time from the real, pre-existing
hallucination_rate metric instead).

Reversible: `downgrade` drops the table -- purely additive.

Revision ID: 0123
Revises: 0122
Create Date: 2026-09-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0123"
down_revision: Union[str, None] = "0122"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_failures",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("evaluation_job_id", sa.Uuid(), sa.ForeignKey("evaluation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(20), nullable=False, server_default="other"),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_evaluation_failures_evaluation_job_id", "evaluation_failures", ["evaluation_job_id"])


def downgrade() -> None:
    op.drop_table("evaluation_failures")
