"""add two_factor_recovery_codes table

RLS is enabled inline here rather than in a follow-up migration (unlike
0002, which enabled it retroactively for tables that already existed) --
this table is new, so there's no reason to ship it even briefly without
the same defense-in-depth every other table already has.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "two_factor_recovery_codes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_two_factor_recovery_codes_user_id", "two_factor_recovery_codes", ["user_id"])
    op.execute("ALTER TABLE public.two_factor_recovery_codes ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("two_factor_recovery_codes")
