"""add agent permission fields (Partie 5.3.7)

Revision ID: 0059
Revises: 0058
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0059"
down_revision: Union[str, None] = "0058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("allowed_users", sa.JSON(), nullable=True))
    op.add_column("agents", sa.Column("allowed_roles", sa.JSON(), nullable=True))
    op.add_column("agents", sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("agents", "is_public")
    op.drop_column("agents", "allowed_roles")
    op.drop_column("agents", "allowed_users")
