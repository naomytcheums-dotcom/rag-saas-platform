"""Hardening Mission, §30 -- persist a knowledge base's description.

`POST /v1/knowledge-bases` accepted `description` and echoed it back in its
response, but `workspaces` had no column for it, so the value was silently
dropped (a create followed by a read lost it). Purely additive and
nullable: every pre-existing workspace stays exactly as it was.

Reversible: `downgrade` drops the column (the stored descriptions are lost,
by definition -- nothing else references them).

Revision ID: 0132
Revises: 0131
Create Date: 2026-10-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0132"
down_revision: Union[str, None] = "0131"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("workspaces", "description")
