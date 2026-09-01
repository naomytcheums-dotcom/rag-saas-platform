"""add account_restore_tokens table

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_restore_tokens",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_account_restore_tokens_user_id", "account_restore_tokens", ["user_id"])
    op.create_index("ix_account_restore_tokens_token_hash", "account_restore_tokens", ["token_hash"], unique=True)
    op.execute("ALTER TABLE public.account_restore_tokens ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("account_restore_tokens")
