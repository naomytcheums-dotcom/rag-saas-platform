"""widget_configs + widget_suggested_questions (9.3)

Revision ID: 0085
Revises: 0084
Create Date: 2026-09-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0085"
down_revision: Union[str, None] = "0084"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "widget_configs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("public_key", sa.String(64), nullable=False),
        sa.Column("logo_url", sa.String(1024), nullable=True),
        sa.Column("primary_color", sa.String(9), nullable=False, server_default="#6C63FF"),
        sa.Column("secondary_color", sa.String(9), nullable=False, server_default="#4A47A3"),
        sa.Column("text_color", sa.String(9), nullable=False, server_default="#FFFFFF"),
        sa.Column("background_color", sa.String(9), nullable=False, server_default="#FFFFFF"),
        sa.Column("header_background", sa.String(9), nullable=False, server_default="#6C63FF"),
        sa.Column("border_radius", sa.String(16), nullable=False, server_default="12px"),
        sa.Column("font_family", sa.String(128), nullable=False, server_default="system-ui"),
        sa.Column("widget_name", sa.String(50), nullable=False, server_default="Assistant IA"),
        sa.Column("widget_name_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("widget_short_name", sa.String(12), nullable=True),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("avatar_uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("avatar_updated_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("use_default_avatar", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("welcome_message", sa.Text(), nullable=True),
        sa.Column("welcome_message_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("welcome_message_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("welcome_message_updated_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("position", sa.String(16), nullable=False, server_default="bottom-right"),
        sa.Column("position_mobile", sa.String(16), nullable=True),
        sa.Column("offset_x", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("offset_y", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("position_locked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("language", sa.String(8), nullable=False, server_default="en"),
        sa.Column("auto_detect_language", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("theme", sa.String(8), nullable=False, server_default="auto"),
        sa.Column("theme_custom_css", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", name="uq_widget_configs_organization_id"),
        sa.UniqueConstraint("public_key", name="uq_widget_configs_public_key"),
    )
    op.create_index("ix_widget_configs_organization_id", "widget_configs", ["organization_id"])
    op.create_index("ix_widget_configs_public_key", "widget_configs", ["public_key"])

    op.create_table(
        "widget_suggested_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("widget_config_id", sa.Uuid(), sa.ForeignKey("widget_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("label", sa.String(64), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_widget_suggested_questions_widget_config_id", "widget_suggested_questions", ["widget_config_id"])


def downgrade() -> None:
    op.drop_table("widget_suggested_questions")
    op.drop_table("widget_configs")
