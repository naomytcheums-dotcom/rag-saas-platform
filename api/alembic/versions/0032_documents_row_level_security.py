"""enable row level security on documents/document_chunks (fixes 0031)

Migration 0031 created these two tables but forgot the ENABLE ROW LEVEL
SECURITY statement every application table has had since migration
0002 (inline in every migration since 0014) --
tests/test_postgres_integration.py's own
test_every_application_table_has_row_level_security_enabled caught it
in CI. Fixed here as a follow-up migration rather than editing 0031 in
place -- 0031 was already applied to the real dev database by the time
this was found, and rewriting an already-applied migration's history is
worse than a small follow-up fix.

Revision ID: 0032
Revises: 0031
Create Date: 2026-09-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.document_chunks ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.document_chunks DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.documents DISABLE ROW LEVEL SECURITY")
