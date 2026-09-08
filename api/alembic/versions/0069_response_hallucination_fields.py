"""add responses.* fields for Partie 6.2.4/6.2.6/6.2.7/6.2.8/6.2.9/6.2.10

Revision ID: 0069
Revises: 0068
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0069"
down_revision: Union[str, None] = "0068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("responses", sa.Column("confidence_estimation", sa.Float(), nullable=True))
    op.add_column("responses", sa.Column("confidence_estimation_factors", sa.JSON(), nullable=True))
    op.add_column("responses", sa.Column("claim_verification_status", sa.String(length=20), nullable=True))
    op.add_column("responses", sa.Column("claim_verification_details", sa.JSON(), nullable=True))
    op.add_column("responses", sa.Column("has_contradictions", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("responses", sa.Column("contradictions", sa.JSON(), nullable=True))
    op.add_column("responses", sa.Column("source_consistency_score", sa.Float(), nullable=True))
    op.add_column("responses", sa.Column("source_consistency_details", sa.JSON(), nullable=True))
    op.add_column("responses", sa.Column("hallucination_score", sa.Float(), nullable=True))
    op.add_column("responses", sa.Column("hallucination_factors", sa.JSON(), nullable=True))
    op.add_column("responses", sa.Column("groundedness_score", sa.Float(), nullable=True))
    op.add_column("responses", sa.Column("groundedness_factors", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("responses", "groundedness_factors")
    op.drop_column("responses", "groundedness_score")
    op.drop_column("responses", "hallucination_factors")
    op.drop_column("responses", "hallucination_score")
    op.drop_column("responses", "source_consistency_details")
    op.drop_column("responses", "source_consistency_score")
    op.drop_column("responses", "contradictions")
    op.drop_column("responses", "has_contradictions")
    op.drop_column("responses", "claim_verification_details")
    op.drop_column("responses", "claim_verification_status")
    op.drop_column("responses", "confidence_estimation_factors")
    op.drop_column("responses", "confidence_estimation")
