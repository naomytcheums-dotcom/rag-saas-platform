"""Enable RLS on the 11 tables created by migrations 0116-0127 without the
`ENABLE ROW LEVEL SECURITY` line every other table has had since migration
0014, found by `tests/test_postgres_integration.py::test_every_application_table_has_row_level_security_enabled`
failing against the real database during the Hardening Mission regression run.

On Supabase a table without RLS is reachable through the public REST API with the
project's anon key, so this is a real exposure (conversation-adjacent data such as
notifications, retrieval diagnostics, flight recordings, long-term agent memory),
not a style issue. Same remedy as migration 0110: RLS enabled with ZERO policies,
so Postgres' default-deny applies to every non-bypassing role. The application
connects with a role that bypasses RLS and already scopes every query by
organization_id, so no existing query changes behavior.

`IF EXISTS` keeps the migration safe on a database where one of these tables was
never created. Reversible: `downgrade` disables RLS again.

Revision ID: 0131
Revises: 0130
Create Date: 2026-10-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0131"
down_revision: Union[str, None] = "0130"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    "agent_long_term_memory_items",
    "evaluation_failures",
    "flight_recordings",
    "mcp_server_configs",
    "mcp_tool_cache",
    "notification_preferences",
    "notifications",
    "rag_experiments",
    "retrieval_diagnostics",
    "sandbox_environments",
    "workflow_node_executions",
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE IF EXISTS public.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE IF EXISTS public.{table} DISABLE ROW LEVEL SECURITY")
