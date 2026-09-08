"""add conversations.deleted_at + conversations.is_public (Partie 8.1.13/8.1.16)

Revision ID: 0079
Revises: 0078
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0079"
down_revision: Union[str, None] = "0078"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("conversations", sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"))
    op.create_index("ix_conversations_deleted_at", "conversations", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_conversations_deleted_at", table_name="conversations")
    op.drop_column("conversations", "is_public")
    op.drop_column("conversations", "deleted_at")
