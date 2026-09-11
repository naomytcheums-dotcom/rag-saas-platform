"""Partie 16 (ter), extended -- real plugin versioning + execution:
plugins.category, plugins.install_count, plugin_versions,
plugin_executions.

Revision ID: 0096
Revises: 0095
Create Date: 2026-09-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0096"
down_revision: Union[str, None] = "0095"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    plugin_category = sa.Enum(
        "analytics", "automation", "communication", "data", "integration", "productivity", "security", "other",
        name="plugincategory",
    )
    plugin_execution_status = sa.Enum("success", "error", "timeout", name="pluginexecutionstatus")

    # add_column, unlike create_table, does NOT auto-create the enum
    # type -- must be created explicitly first (a real bug found while
    # running this migration).
    plugin_category.create(op.get_bind(), checkfirst=True)
    op.add_column("plugins", sa.Column("category", plugin_category, nullable=False, server_default="other"))
    op.add_column("plugins", sa.Column("install_count", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "plugin_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("plugin_id", sa.Uuid(), sa.ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("code_key", sa.String(500), nullable=False),
        sa.Column("code_size_bytes", sa.Integer(), nullable=False),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("plugin_id", "version", name="uq_plugin_version"),
    )
    op.create_index("ix_plugin_versions_plugin_id", "plugin_versions", ["plugin_id"])

    op.create_table(
        "plugin_executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("plugin_id", sa.Uuid(), sa.ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("installation_id", sa.Uuid(), sa.ForeignKey("plugin_installations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("hook", sa.String(50), nullable=True),
        sa.Column("status", plugin_execution_status, nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_plugin_executions_plugin_id", "plugin_executions", ["plugin_id"])
    op.create_index("ix_plugin_executions_organization_id", "plugin_executions", ["organization_id"])
    op.create_index("ix_plugin_executions_created_at", "plugin_executions", ["created_at"])


def downgrade() -> None:
    op.drop_table("plugin_executions")
    sa.Enum(name="pluginexecutionstatus").drop(op.get_bind(), checkfirst=True)
    op.drop_table("plugin_versions")
    op.drop_column("plugins", "install_count")
    op.drop_column("plugins", "category")
    sa.Enum(name="plugincategory").drop(op.get_bind(), checkfirst=True)
