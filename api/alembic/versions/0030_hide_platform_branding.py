"""add hide_platform_branding to organization_branding (Partie 1.4.6)

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organization_branding", sa.Column("hide_platform_branding", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("organization_branding", "hide_platform_branding")
