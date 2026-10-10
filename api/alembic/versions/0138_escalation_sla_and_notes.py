"""Escalation tickets: SLA deadline and internal notes (spec 15.1.4 and 15.1.6).

Adds `escalations.sla_due_at` (nullable) and the `escalation_notes` table. Additive and reversible. Row level security is enabled on the
new table like on every other table since 0131.

Revision ID: 0138
Revises: 0137
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0138"
down_revision: str | None = "0137"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("escalations", sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "escalation_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("escalation_id", sa.Uuid(), sa.ForeignKey("escalations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_escalation_notes_escalation_id", "escalation_notes", ["escalation_id"])
    op.execute("ALTER TABLE escalation_notes ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("escalation_notes")
    op.drop_column("escalations", "sla_due_at")
