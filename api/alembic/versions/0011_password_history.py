"""add password_history table (audit finding 15 -- password reuse protection)

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_history",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_password_history_user_id", "password_history", ["user_id"])
    op.create_index("ix_password_history_created_at", "password_history", ["created_at"])
    op.execute("ALTER TABLE public.password_history ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("password_history")
