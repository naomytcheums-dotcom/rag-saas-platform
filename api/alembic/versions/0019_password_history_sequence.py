"""add password_history.sequence -- fix non-deterministic history ordering

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-02

Real bug, found via a flake in real CI (not local SQLite, which never
reproduces it): api/security/password_history.py ordered "most recent N
rows" by `created_at DESC` alone. Two rows written in fast succession
can share the same microsecond-truncated timestamp; `id` (random UUID
v4) can't break that tie meaningfully, so Postgres's order for tied rows
is genuinely undefined -- which row got pruned as "stale" varied between
runs. `sequence` is a monotonic-per-user counter that can never tie --
assigned explicitly in application code (api/security/password_history.py's
record_password_change), not a DB IDENTITY column: a first attempt at
this migration used one, and it broke the entire fast test suite (SQLite
has no equivalent for an identity column on a non-primary-key, and that
suite builds its schema from the ORM models directly, not via Alembic).

Existing rows (dev/test artifacts predating this fix, not real user
data) are backfilled best-effort via ROW_NUMBER() ordered by the exact
created_at/id pair the old, buggy code used -- there is no way to
recover their TRUE original insertion order once already collapsed into
that ambiguity, and there is nothing here worth being more careful for.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("password_history", sa.Column("sequence", sa.BigInteger(), nullable=True))
    op.execute("""
        UPDATE password_history
        SET sequence = backfilled.row_number
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at, id) AS row_number
            FROM password_history
        ) AS backfilled
        WHERE password_history.id = backfilled.id
    """)
    op.alter_column("password_history", "sequence", nullable=False)
    op.create_unique_constraint("uq_password_history_user_sequence", "password_history", ["user_id", "sequence"])


def downgrade() -> None:
    op.drop_constraint("uq_password_history_user_sequence", "password_history", type_="unique")
    op.drop_column("password_history", "sequence")
