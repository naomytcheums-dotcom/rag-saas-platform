"""Plans: `max_questions_per_day` (spec 12.2.1 - 12.2.5: Free 10 questions a day, Starter 500, Pro and above unlimited).

Revision ID: 0145
Revises: 0144

Additive and reversible. The new column is NULL (= unlimited) for every existing plan, except the two catalogue plans whose daily limit the specification states and
whose rows already exist in a database created by the application's seed: `free` gets 10 and `starter` 500, but ONLY while the column is still NULL, so a value set
by the owner is never overwritten. Document limits of existing rows are deliberately NOT touched here: changing `max_documents` of a live plan changes what existing
customers may do and is the owner's decision (PATCH /admin/plans/{id}); new databases get the specified values from the seed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0145"
down_revision: str | None = "0144"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("max_questions_per_day", sa.Integer(), nullable=True))
    op.execute("UPDATE plans SET max_questions_per_day = 10 WHERE key = 'free' AND max_questions_per_day IS NULL")
    op.execute("UPDATE plans SET max_questions_per_day = 500 WHERE key = 'starter' AND max_questions_per_day IS NULL")


def downgrade() -> None:
    op.drop_column("plans", "max_questions_per_day")
