"""add custom_tools table (Partie 5.2.10)

Revision ID: 0064
Revises: 0063
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0064"
down_revision: Union[str, None] = "0063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_tools",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("webhook_url", sa.String(length=2000), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False, server_default="POST"),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("timeout", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("schema", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_tools_organization_id", "custom_tools", ["organization_id"])
    op.execute("ALTER TABLE public.custom_tools ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.custom_tools DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_custom_tools_organization_id", table_name="custom_tools")
    op.drop_table("custom_tools")
