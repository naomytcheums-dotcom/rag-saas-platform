"""add custom email-domain verification columns to custom_domains (Partie 1.4.5)

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("custom_domains", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("custom_domains", sa.Column("dkim_selector", sa.String(length=63), nullable=True))
    op.add_column("custom_domains", sa.Column("dkim_private_key", sa.Text(), nullable=True))
    op.add_column("custom_domains", sa.Column("dkim_public_key", sa.Text(), nullable=True))
    op.add_column("custom_domains", sa.Column("email_verification_token", sa.String(length=64), nullable=True))
    op.add_column("custom_domains", sa.Column("email_verification_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("custom_domains", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("custom_domains", sa.Column("email_verification_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("custom_domains", sa.Column("resend_domain_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("custom_domains", "resend_domain_id")
    op.drop_column("custom_domains", "email_verification_started_at")
    op.drop_column("custom_domains", "email_verified_at")
    op.drop_column("custom_domains", "email_verification_attempts")
    op.drop_column("custom_domains", "email_verification_token")
    op.drop_column("custom_domains", "dkim_public_key")
    op.drop_column("custom_domains", "dkim_private_key")
    op.drop_column("custom_domains", "dkim_selector")
    op.drop_column("custom_domains", "email_verified")
