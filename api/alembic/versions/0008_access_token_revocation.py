"""add revoked_access_tokens table and sessions.access_token_jti

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("access_token_jti", sa.String(36), nullable=True))

    op.create_table(
        "revoked_access_tokens",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("jti", sa.String(36), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_access_tokens_jti", "revoked_access_tokens", ["jti"], unique=True)
    op.create_index("ix_revoked_access_tokens_user_id", "revoked_access_tokens", ["user_id"])
    op.execute("ALTER TABLE public.revoked_access_tokens ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("revoked_access_tokens")
    op.drop_column("sessions", "access_token_jti")
