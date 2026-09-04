"""add deleted_at/deleted_by to documents (Partie 2.2.8)

Revision ID: 0036
Revises: 0035
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("deleted_by", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_documents_deleted_by_users", "documents", "users", ["deleted_by"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_documents_deleted_by_users", "documents", type_="foreignkey")
    op.drop_column("documents", "deleted_by")
    op.drop_column("documents", "deleted_at")
