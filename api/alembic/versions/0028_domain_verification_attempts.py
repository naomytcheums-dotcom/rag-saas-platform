"""add verification_attempts/last_verification_attempt_at to custom_domains (Partie 1.4.4)

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("custom_domains", sa.Column("verification_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("custom_domains", sa.Column("last_verification_attempt_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("custom_domains", "last_verification_attempt_at")
    op.drop_column("custom_domains", "verification_attempts")
