"""add tool_permissions table (Partie 5.1.3)

Revision ID: 0049
Revises: 0048
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.String(length=200), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("permission", sa.String(length=10), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "agent_id", "user_id", "tool_name", name="uq_tool_permissions_scope"),
    )
    op.create_index("ix_tool_permissions_organization_id", "tool_permissions", ["organization_id"])
    op.create_index("ix_tool_permissions_lookup", "tool_permissions", ["organization_id", "agent_id", "user_id", "tool_name"])
    op.execute("ALTER TABLE public.tool_permissions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.tool_permissions DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_tool_permissions_lookup", table_name="tool_permissions")
    op.drop_index("ix_tool_permissions_organization_id", table_name="tool_permissions")
    op.drop_table("tool_permissions")
