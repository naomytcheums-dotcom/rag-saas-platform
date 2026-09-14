"""Partie 24 -- fine-tuning: datasets, jobs, fine-tuned models, and
evaluation (a real, thin summary over the existing Evaluation Lab's
own real evaluation_jobs table -- see api/models/fine_tuning.py's own
module docstring).

Revision ID: 0108
Revises: 0107
Create Date: 2026-09-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0108"
down_revision: Union[str, None] = "0107"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fine_tuning_datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dataset_type", sa.String(length=20), nullable=False, server_default="llm"),
        sa.Column("format", sa.String(length=20), nullable=False, server_default="jsonl"),
        sa.Column("file_key", sa.String(length=1024), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("validation_errors", sa.JSON(), nullable=True),
        sa.Column("example_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fine_tuning_datasets_organization_id", "fine_tuning_datasets", ["organization_id"])
    op.execute("ALTER TABLE public.fine_tuning_datasets ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "fine_tuning_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("base_model", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("hyperparameters", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("provider_job_id", sa.String(length=200), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_id"], ["fine_tuning_datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fine_tuning_jobs_organization_id", "fine_tuning_jobs", ["organization_id"])
    op.create_index("ix_fine_tuning_jobs_dataset_id", "fine_tuning_jobs", ["dataset_id"])
    op.execute("ALTER TABLE public.fine_tuning_jobs ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "fine_tuned_models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_model_id", sa.String(length=300), nullable=False),
        sa.Column("base_model", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="available"),
        sa.Column("deployed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["fine_tuning_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fine_tuned_models_organization_id", "fine_tuned_models", ["organization_id"])
    op.create_index("ix_fine_tuned_models_job_id", "fine_tuned_models", ["job_id"])
    op.execute("ALTER TABLE public.fine_tuned_models ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "fine_tuning_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_job_id", sa.Uuid(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("score", sa.Numeric(6, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["fine_tuned_models.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_id"], ["evaluation_datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluation_job_id"], ["evaluation_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fine_tuning_evaluations_model_id", "fine_tuning_evaluations", ["model_id"])
    op.create_index("ix_fine_tuning_evaluations_dataset_id", "fine_tuning_evaluations", ["dataset_id"])
    op.execute("ALTER TABLE public.fine_tuning_evaluations ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("fine_tuning_evaluations")
    op.drop_table("fine_tuned_models")
    op.drop_table("fine_tuning_jobs")
    op.drop_table("fine_tuning_datasets")
