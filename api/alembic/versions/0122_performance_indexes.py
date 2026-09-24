"""Phase 5, Étape 13 -- Performance: 5 real, measured index gaps found
by auditing this étape's own explicit critical-column list against
every actual `__table_args__`/`index=True` in api/models/. Every other
column on that list (documents.organization_id, conversations.user_id,
messages.conversation_id, agent_runs.agent_id, evaluation_jobs.dataset_id,
notifications.user_id/organization_id/created_at, audit_logs.user_id+
timestamp, ...) was already indexed -- confirmed by direct reads, not
assumed. Only the genuinely missing ones are added here:

- conversations.organization_id -- the model's own docstring already
  flags this column as "useful for a future real 'conversations in my
  organization' admin view" but never got the index that view needs.
- workflow_runs.status -- a worker/dashboard listing pending/running
  runs scans the whole table without this.
- agent_runs.status -- same pattern as workflow_runs.
- evaluation_jobs.status -- Eval Lab's own "running jobs" list has the
  same gap.
- notifications (user_id, read_at) composite -- the model's own
  __table_args__ comment already names the exact query this covers
  ("every real list query filters by (user_id, organization_id),
  optionally + read_at IS NULL for the unread-count endpoint") but no
  index existed for it; user_id alone (already indexed) still means a
  per-user scan for the unread count.

Reversible: `downgrade` drops exactly the 5 indexes added here.

Revision ID: 0122
Revises: 0121
Create Date: 2026-09-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0122"
down_revision: Union[str, None] = "0121"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_conversations_organization_id", "conversations", ["organization_id"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_evaluation_jobs_status", "evaluation_jobs", ["status"])
    op.create_index("ix_notifications_user_id_read_at", "notifications", ["user_id", "read_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id_read_at", table_name="notifications")
    op.drop_index("ix_evaluation_jobs_status", table_name="evaluation_jobs")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_workflow_runs_status", table_name="workflow_runs")
    op.drop_index("ix_conversations_organization_id", table_name="conversations")
