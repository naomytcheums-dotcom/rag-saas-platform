"""slack/teams/discord chat-platform integrations (9.4)

Revision ID: 0086
Revises: 0085
Create Date: 2026-09-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0086"
down_revision: Union[str, None] = "0085"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "slack_integrations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(32), nullable=False),
        sa.Column("team_name", sa.String(255), nullable=True),
        sa.Column("bot_token", sa.Text(), nullable=False),
        sa.Column("user_token", sa.Text(), nullable=True),
        sa.Column("webhook_url", sa.String(1024), nullable=True),
        sa.Column("default_channel", sa.String(64), nullable=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", name="uq_slack_integrations_organization_id"),
    )
    op.create_index("ix_slack_integrations_organization_id", "slack_integrations", ["organization_id"])

    op.create_table(
        "slack_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("integration_id", sa.Uuid(), sa.ForeignKey("slack_integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("slack_message_ts", sa.String(32), nullable=False),
        sa.Column("slack_channel", sa.String(64), nullable=False),
        sa.Column("slack_user_id", sa.String(32), nullable=False),
        sa.Column("slack_user_name", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("thread_ts", sa.String(32), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_slack_messages_integration_id", "slack_messages", ["integration_id"])

    op.create_table(
        "teams_integrations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=True),
        sa.Column("team_id", sa.String(64), nullable=True),
        sa.Column("team_name", sa.String(255), nullable=True),
        sa.Column("bot_id", sa.String(64), nullable=True),
        sa.Column("bot_token", sa.Text(), nullable=True),
        sa.Column("webhook_url", sa.String(1024), nullable=True),
        sa.Column("default_channel", sa.String(64), nullable=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", name="uq_teams_integrations_organization_id"),
    )
    op.create_index("ix_teams_integrations_organization_id", "teams_integrations", ["organization_id"])

    op.create_table(
        "teams_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("integration_id", sa.Uuid(), sa.ForeignKey("teams_integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("teams_message_id", sa.String(128), nullable=False),
        sa.Column("teams_channel", sa.String(128), nullable=False),
        sa.Column("teams_user_id", sa.String(128), nullable=False),
        sa.Column("teams_user_name", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("reply_to_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_teams_messages_integration_id", "teams_messages", ["integration_id"])

    op.create_table(
        "discord_integrations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guild_id", sa.String(32), nullable=False),
        sa.Column("guild_name", sa.String(255), nullable=True),
        sa.Column("bot_token", sa.Text(), nullable=False),
        sa.Column("bot_id", sa.String(32), nullable=True),
        sa.Column("default_channel_id", sa.String(32), nullable=True),
        sa.Column("default_channel_name", sa.String(255), nullable=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", name="uq_discord_integrations_organization_id"),
    )
    op.create_index("ix_discord_integrations_organization_id", "discord_integrations", ["organization_id"])

    op.create_table(
        "discord_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("integration_id", sa.Uuid(), sa.ForeignKey("discord_integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("discord_message_id", sa.String(32), nullable=False),
        sa.Column("discord_channel_id", sa.String(32), nullable=False),
        sa.Column("discord_user_id", sa.String(32), nullable=False),
        sa.Column("discord_user_name", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("is_thread", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("parent_message_id", sa.String(32), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_discord_messages_integration_id", "discord_messages", ["integration_id"])


def downgrade() -> None:
    op.drop_table("discord_messages")
    op.drop_table("discord_integrations")
    op.drop_table("teams_messages")
    op.drop_table("teams_integrations")
    op.drop_table("slack_messages")
    op.drop_table("slack_integrations")
