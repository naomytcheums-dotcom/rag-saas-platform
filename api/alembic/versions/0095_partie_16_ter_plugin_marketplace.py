"""Partie 16 (ter) -- plugin marketplace: plugins, plugin_installations,
plugin_reviews.

Revision ID: 0095
Revises: 0094
Create Date: 2026-09-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0095"
down_revision: Union[str, None] = "0094"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    plugin_status = sa.Enum("pending", "approved", "rejected", "suspended", name="pluginstatus")

    op.create_table(
        "plugins",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("code_key", sa.String(500), nullable=False),
        sa.Column("code_size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", plugin_status, nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_plugins_organization_id", "plugins", ["organization_id"])

    op.create_table(
        "plugin_installations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("plugin_id", sa.Uuid(), sa.ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("installed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("installed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("plugin_id", "organization_id", name="uq_plugin_installation_org"),
    )
    op.create_index("ix_plugin_installations_plugin_id", "plugin_installations", ["plugin_id"])
    op.create_index("ix_plugin_installations_organization_id", "plugin_installations", ["organization_id"])

    op.create_table(
        "plugin_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("plugin_id", sa.Uuid(), sa.ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("plugin_id", "user_id", name="uq_plugin_review_user"),
    )
    op.create_index("ix_plugin_reviews_plugin_id", "plugin_reviews", ["plugin_id"])


def downgrade() -> None:
    op.drop_table("plugin_reviews")
    op.drop_table("plugin_installations")
    op.drop_table("plugins")
    sa.Enum(name="pluginstatus").drop(op.get_bind(), checkfirst=True)
