"""Add `message_feedback.correction` (spec 15.2.4: the answer the user proposes). Nullable, additive, reversible.

Revision ID: 0139
Revises: 0138
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0139"
down_revision: str | None = "0138"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("message_feedback", sa.Column("correction", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("message_feedback", "correction")
