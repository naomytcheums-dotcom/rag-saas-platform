"""Phase 5, Étape 11 -- real, additive table: `workflow_node_executions`,
the same real per-step tracing gap `agent_traces` already closed for
agents, now closed for workflows. See
api/models/workflow_node_execution.py's own docstring.

Reversible: `downgrade` drops the table -- purely additive.

Revision ID: 0120
Revises: 0119
Create Date: 2026-09-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0120"
down_revision: Union[str, None] = "0119"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_node_executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workflow_run_id", sa.Uuid(), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.String(64), nullable=False),
        sa.Column("node_type", sa.String(50), nullable=False),
        sa.Column("input", sa.JSON(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="started"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_node_executions_workflow_run_id", "workflow_node_executions", ["workflow_run_id"])


def downgrade() -> None:
    op.drop_table("workflow_node_executions")
