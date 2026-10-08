"""Systèmes internes, item 19 -- real, additive table: `rag_experiments`
(Experiment Lab / RAG Genome). See api/models/rag_experiment.py's own
module docstring for the full real design -- a versioned history of
every tested RAG configuration, linked to the real `EvaluationJob` rows
item 18's `run_evolution_cycle` already produces, keyed by a real,
deterministic config hash (api.services.rag_genome.compute_config_hash).

Reversible: `downgrade` drops the table -- purely additive.

Revision ID: 0126
Revises: 0125
Create Date: 2026-09-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0126"
down_revision: Union[str, None] = "0125"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rag_experiments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("baseline_job_id", sa.Uuid(), sa.ForeignKey("evaluation_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("candidate_job_id", sa.Uuid(), sa.ForeignKey("evaluation_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decision", sa.String(30), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_rag_experiments_organization_id", "rag_experiments", ["organization_id"])
    op.create_index("ix_rag_experiments_config_hash", "rag_experiments", ["config_hash"])


def downgrade() -> None:
    op.drop_table("rag_experiments")
