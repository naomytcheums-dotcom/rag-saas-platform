"""add consent_reactivation_tokens table

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "consent_reactivation_tokens",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_consent_reactivation_tokens_user_id", "consent_reactivation_tokens", ["user_id"])
    op.create_index("ix_consent_reactivation_tokens_token_hash", "consent_reactivation_tokens", ["token_hash"], unique=True)
    op.execute("ALTER TABLE public.consent_reactivation_tokens ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("consent_reactivation_tokens")
