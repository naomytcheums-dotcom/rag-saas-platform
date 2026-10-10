"""Add `users.job_title` (spec 1.1.13: profile with company and role). Nullable, additive, reversible.

Revision ID: 0142
Revises: 0141
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0142"
down_revision: str | None = "0141"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("job_title", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "job_title")
