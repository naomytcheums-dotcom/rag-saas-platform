"""add resource_permissions (Etape 1.2.8 -- granular per-resource permissions)

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resource_permissions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("granted_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_resource_permissions_organization_id", "resource_permissions", ["organization_id"])
    op.create_index("ix_resource_permissions_user_id", "resource_permissions", ["user_id"])
    op.create_index("ix_resource_permissions_resource", "resource_permissions", ["resource_type", "resource_id"])
    op.create_unique_constraint(
        "uq_resource_permissions_org_resource_user_action", "resource_permissions",
        ["organization_id", "resource_type", "resource_id", "user_id", "action"],
    )
    op.execute("ALTER TABLE public.resource_permissions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("resource_permissions")
