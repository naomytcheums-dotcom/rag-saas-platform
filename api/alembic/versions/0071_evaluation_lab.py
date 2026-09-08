"""add evaluation_datasets/evaluation_questions/question_sets/question_set_items/benchmark_versions (Partie 7.1.1-7.1.6)

Revision ID: 0071
Revises: 0070
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0071"
down_revision: Union[str, None] = "0070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_evaluation_datasets_organization_id", "evaluation_datasets", ["organization_id"])

    op.create_table(
        "evaluation_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("expected_documents", sa.JSON(), nullable=True),
        sa.Column("difficulty", sa.String(length=10), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expected_answer_type", sa.String(length=10), nullable=True),
        sa.Column("expected_answer_metadata", sa.JSON(), nullable=True),
    )
    op.create_index("ix_evaluation_questions_dataset_id", "evaluation_questions", ["dataset_id"])

    op.create_table(
        "question_sets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_question_sets_dataset_id", "question_sets", ["dataset_id"])

    op.create_table(
        "question_set_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("question_set_id", sa.Uuid(), sa.ForeignKey("question_sets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("question_set_id", "question_id", name="uq_question_set_items_set_question"),
    )
    op.create_index("ix_question_set_items_question_set_id", "question_set_items", ["question_set_id"])
    op.create_index("ix_question_set_items_question_id", "question_set_items", ["question_id"])

    op.create_table(
        "benchmark_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("question_set_id", sa.Uuid(), sa.ForeignKey("question_sets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("dataset_id", "version_number", name="uq_benchmark_versions_dataset_version"),
    )
    op.create_index("ix_benchmark_versions_dataset_id", "benchmark_versions", ["dataset_id"])


def downgrade() -> None:
    op.drop_table("benchmark_versions")
    op.drop_table("question_set_items")
    op.drop_table("question_sets")
    op.drop_table("evaluation_questions")
    op.drop_table("evaluation_datasets")
