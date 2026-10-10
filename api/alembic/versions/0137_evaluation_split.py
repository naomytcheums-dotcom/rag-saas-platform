"""Add the tuning / held-out split to the Eval Lab (spec 7.1.7).

`evaluation_questions.split` marks a question as "tuning" or "held_out" (NULL = not assigned, treated as tuning) and
`evaluation_jobs.split` lets a job evaluate only one side, so the score reported on held-out questions is never the one the
RAG was tuned on. Additive and reversible: both columns are nullable and the downgrade drops them.

Revision ID: 0137
Revises: 0136
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0137"
down_revision: str | None = "0136"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("evaluation_questions", sa.Column("split", sa.String(10), nullable=True))
    op.add_column("evaluation_jobs", sa.Column("split", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("evaluation_jobs", "split")
    op.drop_column("evaluation_questions", "split")
