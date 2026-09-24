"""sandbox_environments

Revision ID: 0124
Revises: 0123
Create Date: 2026-09-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0124"
down_revision: Union[str, None] = "0123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sandbox_environments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("api_key_id", sa.UUID(), nullable=True),
        sa.Column("data_ttl_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["api_key_id"], ["organization_api_keys.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sandbox_environments_organization_id", "sandbox_environments", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_sandbox_environments_organization_id", table_name="sandbox_environments")
    op.drop_table("sandbox_environments")
