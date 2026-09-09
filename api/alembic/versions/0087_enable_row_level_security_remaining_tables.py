"""enable row level security on every table still missing it

Real, honest gap found by tests/test_postgres_integration.py's own
`test_every_application_table_has_row_level_security_enabled`:
migrations 0002/0032/0037 enabled RLS on every table that existed
through migration 0066 (Responses and Citations) -- but no migration
since then (Partie 6.1 onward, including this project's own 9.1-9.4
batch) ever added the same real `ENABLE ROW LEVEL SECURITY` step for
its own new tables. Same real, zero-policy, defense-in-depth reasoning
as 0002's own docstring: this app's backend connects with a role that
bypasses RLS by default, so this changes nothing for real reads/writes
-- it only closes the real gap Supabase's own Advisor flags for any
OTHER access path (e.g. a PostgREST/Data API key) ever pointed at
these tables.

Revision ID: 0087
Revises: 0086
Create Date: 2026-09-09
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0087"
down_revision: Union[str, None] = "0086"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    "ab_tests", "agent_api_keys", "agent_memory_items", "agent_runs", "agent_sessions", "agent_traces", "agents",
    "batch_job_items", "batch_jobs", "benchmark_versions", "call_records", "citations", "comparison_jobs",
    "conversation_messages", "conversation_shares", "conversations", "custom_tools", "deployment_evaluations",
    "discord_integrations", "discord_messages", "document_audit_logs", "document_entities", "document_images",
    "document_keywords", "document_tag_assignments", "document_tags", "document_versions", "escalations",
    "evaluation_datasets", "evaluation_jobs", "evaluation_questions", "evaluation_results", "external_sources",
    "follow_up_questions", "human_approvals", "key_rotation_history", "llm_fallbacks", "manual_evaluations",
    "message_edit_history", "message_feedback", "organization_api_keys", "question_set_items", "question_sets",
    "regeneration_history", "regression_detections", "regression_thresholds", "reindex_schedules", "responses",
    "slack_integrations", "slack_messages", "task_plans", "task_steps", "teams_integrations", "teams_messages",
    "tool_budgets", "tool_fallbacks", "tool_permissions", "tool_timeout_overrides", "voice_messages",
    "voice_settings", "webhook_deliveries", "webhooks", "widget_configs", "widget_suggested_questions",
    "workflow_human_inputs", "workflow_runs", "workflow_triggers", "workflow_versions", "workflows",
]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
