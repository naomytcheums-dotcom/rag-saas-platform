"""add workflows, workflow_triggers, workflow_runs tables (Partie 5.4.1-5.4.11)

Revision ID: 0062
Revises: 0061
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0062"
down_revision: Union[str, None] = "0061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("nodes", sa.JSON(), nullable=False),
        sa.Column("edges", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflows_organization_id", "workflows", ["organization_id"])
    op.create_index("ix_workflows_workspace_id", "workflows", ["workspace_id"])
    op.execute("ALTER TABLE public.workflows ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "workflow_triggers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("webhook_token", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_triggers_workflow_id", "workflow_triggers", ["workflow_id"])
    op.execute("ALTER TABLE public.workflow_triggers ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("input", sa.JSON(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trigger_id"], ["workflow_triggers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_runs_workflow_id", "workflow_runs", ["workflow_id"])
    op.execute("ALTER TABLE public.workflow_runs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.workflow_runs DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_workflow_runs_workflow_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")

    op.execute("ALTER TABLE public.workflow_triggers DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_workflow_triggers_workflow_id", table_name="workflow_triggers")
    op.drop_table("workflow_triggers")

    op.execute("ALTER TABLE public.workflows DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_workflows_workspace_id", table_name="workflows")
    op.drop_index("ix_workflows_organization_id", table_name="workflows")
    op.drop_table("workflows")
