"""Partie 19 -- white-label extended config: the fields organization_branding
(Partie 1.3.10) genuinely didn't have yet (logo/favicon/colors/name/
custom_css/hide_platform_branding were already real -- this only adds
what wasn't there: contact emails, a custom email sender identity,
custom_js, and a real on/off switch for the whole white-label config,
distinct from hide_platform_branding's narrower "hide MY name" toggle).

Revision ID: 0101
Revises: 0100
Create Date: 2026-09-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0101"
down_revision: Union[str, None] = "0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organization_branding", sa.Column("company_email", sa.String(length=254), nullable=True))
    op.add_column("organization_branding", sa.Column("support_email", sa.String(length=254), nullable=True))
    op.add_column("organization_branding", sa.Column("email_sender_name", sa.String(length=200), nullable=True))
    op.add_column("organization_branding", sa.Column("email_sender_email", sa.String(length=254), nullable=True))
    op.add_column("organization_branding", sa.Column("custom_js", sa.Text(), nullable=True))
    op.add_column("organization_branding", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("organization_branding", "is_active")
    op.drop_column("organization_branding", "custom_js")
    op.drop_column("organization_branding", "email_sender_email")
    op.drop_column("organization_branding", "email_sender_name")
    op.drop_column("organization_branding", "support_email")
    op.drop_column("organization_branding", "company_email")
