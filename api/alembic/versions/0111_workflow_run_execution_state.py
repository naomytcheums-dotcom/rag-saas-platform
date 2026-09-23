"""Partie 5.4 -- real execution state on `WorkflowRun`, needed by the
graph executor (`api/services/workflow_engine.py`) this migration
accompanies. Two real, additive columns:

- `context` (JSON): the real, accumulated variable set threaded through
  the graph so far (each block's own `{output_key: result}` merged in
  order) -- read back whenever a run resumes after a real `human`
  block, so the human block's own real answer becomes visible to every
  real block that follows it.
- `current_node_id` (String, nullable): the real node id execution is
  paused at, set only while `status == "waiting_human"`; `NULL` the
  rest of the time (a completed/failed/pending run has no real
  "current" position worth keeping).

`WorkflowRunStatus` also gains a real `waiting_human` value (existing
`pending`/`running`/`completed`/`failed` rows are untouched -- this is
a purely additive enum value, not a rename).

Also adds `workflow_triggers.last_run_at` (nullable): the same real
"reference point for due-ness" column `reindex_schedules.last_run_at`
already established -- `check_scheduled_workflow_triggers` compares a
real `schedule`-type trigger's own cron pattern against this (or
`created_at` for a trigger that has never fired) exactly the way
`check_scheduled_reindexes` already does, no second due-ness mechanism.

Revision ID: 0111
Revises: 0110
Create Date: 2026-09-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0111"
down_revision: Union[str, None] = "0110"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workflow_runs", sa.Column("context", sa.JSON(), nullable=True))
    op.add_column("workflow_runs", sa.Column("current_node_id", sa.String(length=64), nullable=True))
    op.add_column("workflow_triggers", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("workflow_triggers", "last_run_at")
    op.drop_column("workflow_runs", "current_node_id")
    op.drop_column("workflow_runs", "context")
