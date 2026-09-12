"""Partie 21 -- advanced A/B testing: real gaps found in the already
mature Partie 7.3.10 ab_tests system (test_type/target_metric/
min_sample_size/confidence_level/winner columns on ab_tests, plus the
2 genuinely new tables: ab_test_assignments and ab_test_results). See
api/models/evaluation.py's own docstrings for exactly why each is
real and not a duplicate of ab_tests.metrics/get_ab_test_variant.

Revision ID: 0103
Revises: 0102
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0103"
down_revision: Union[str, None] = "0102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ab_tests", sa.Column("test_type", sa.String(length=20), nullable=True))
    op.add_column("ab_tests", sa.Column("target_metric", sa.String(length=50), nullable=True))
    op.add_column("ab_tests", sa.Column("min_sample_size", sa.Integer(), nullable=False, server_default="100"))
    op.add_column("ab_tests", sa.Column("confidence_level", sa.Float(), nullable=False, server_default="0.95"))
    op.add_column("ab_tests", sa.Column("winner", sa.String(length=10), nullable=True))

    op.create_table(
        "ab_test_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ab_test_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=200), nullable=False),
        sa.Column("variant", sa.String(length=1), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ab_test_id"], ["ab_tests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ab_test_id", "request_id", name="uq_ab_test_assignments_test_request"),
    )
    op.create_index("ix_ab_test_assignments_ab_test_id", "ab_test_assignments", ["ab_test_id"])
    op.execute("ALTER TABLE public.ab_test_assignments ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "ab_test_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ab_test_id", sa.Uuid(), nullable=False),
        sa.Column("variant", sa.String(length=1), nullable=False),
        sa.Column("metric_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("mean", sa.Numeric(20, 6), nullable=False),
        sa.Column("std_dev", sa.Numeric(20, 6), nullable=False),
        sa.Column("confidence_interval_lower", sa.Numeric(20, 6), nullable=True),
        sa.Column("confidence_interval_upper", sa.Numeric(20, 6), nullable=True),
        sa.Column("p_value", sa.Numeric(10, 8), nullable=True),
        sa.Column("is_significant", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ab_test_id"], ["ab_tests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ab_test_results_ab_test_id", "ab_test_results", ["ab_test_id"])
    op.execute("ALTER TABLE public.ab_test_results ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("ab_test_results")
    op.drop_table("ab_test_assignments")
    op.drop_column("ab_tests", "winner")
    op.drop_column("ab_tests", "confidence_level")
    op.drop_column("ab_tests", "min_sample_size")
    op.drop_column("ab_tests", "target_metric")
    op.drop_column("ab_tests", "test_type")
