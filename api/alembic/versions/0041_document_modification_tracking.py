"""add last_modified/last_checked to documents (Partie 2.2.13)

Revision ID: 0041
Revises: 0040
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No RLS statement needed here -- two new columns on an already-
    # RLS-enabled table (documents has carried RLS since migration
    # 0002), not a new table.
    op.add_column("documents", sa.Column("last_modified", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("last_checked", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "last_checked")
    op.drop_column("documents", "last_modified")
