"""enable row level security on document_tags/document_tag_assignments/document_versions (fixes 0034/0035)

Migrations 0034 and 0035 created these three tables but forgot the
ENABLE ROW LEVEL SECURITY statement every application table has had
since migration 0002 (inline in every migration since 0014) -- the
SAME real, recurring gotcha migration 0032 already fixed once for
documents/document_chunks (0031's own equivalent miss). Caught the
same way, by tests/test_postgres_integration.py's own
test_every_application_table_has_row_level_security_enabled in CI.
Fixed here as a follow-up migration rather than editing 0034/0035 in
place -- both were already pushed/applied by the time this was found,
and rewriting an already-applied migration's history is worse than a
small follow-up fix.

Revision ID: 0037
Revises: 0036
Create Date: 2026-09-04
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.document_tags ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.document_tag_assignments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.document_versions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.document_versions DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.document_tag_assignments DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.document_tags DISABLE ROW LEVEL SECURITY")
