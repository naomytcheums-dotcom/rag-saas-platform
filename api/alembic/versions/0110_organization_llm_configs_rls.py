"""Enable RLS on organization_llm_configs -- migration 0109 created this
table (storing per-org, encrypted BYOK LLM API keys) without the
`ENABLE ROW LEVEL SECURITY` line every other table has had since
migration 0014, found live by `tests/test_postgres_integration.py`'s
own regression guard (`test_every_application_table_has_row_level_security_enabled`)
failing against the real database in this session. No explicit
policies are added, matching every other table: RLS enabled with zero
policies means Postgres's own default-deny applies to any
non-bypassing role, the same defense-in-depth layer as the rest of the
schema -- app code already scopes every real query by
organization_id, this closes the gap between this one table and that
established, tested invariant, it does not change any existing query
behavior.

Revision ID: 0110
Revises: 0109
Create Date: 2026-09-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0110"
down_revision: Union[str, None] = "0109"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.organization_llm_configs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.organization_llm_configs DISABLE ROW LEVEL SECURITY")
