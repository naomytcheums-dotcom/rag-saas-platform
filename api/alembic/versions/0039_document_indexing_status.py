"""add indexing_started_at/indexing_error to documents (Partie 2.2.11)

Revision ID: 0039
Revises: 0038
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No RLS statement needed here -- these are two new columns on an
    # already-RLS-enabled table (documents has carried RLS since
    # migration 0002), not a new table.
    op.add_column("documents", sa.Column("indexing_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("indexing_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "indexing_error")
    op.drop_column("documents", "indexing_started_at")
