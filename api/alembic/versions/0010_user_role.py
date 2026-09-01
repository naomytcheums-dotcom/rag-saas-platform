"""replace users.is_superadmin with users.role (5.1 -- RBAC prep for Partie 1.2)

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_role_enum = sa.Enum("user", "admin", "superadmin", name="userrole")


def upgrade() -> None:
    user_role_enum.create(op.get_bind(), checkfirst=True)
    op.add_column("users", sa.Column("role", user_role_enum, nullable=False, server_default="user"))
    op.execute("UPDATE users SET role = 'superadmin' WHERE is_superadmin = true")
    op.drop_column("users", "is_superadmin")


def downgrade() -> None:
    op.add_column("users", sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE users SET is_superadmin = true WHERE role = 'superadmin'")
    op.drop_column("users", "role")
    user_role_enum.drop(op.get_bind(), checkfirst=True)
