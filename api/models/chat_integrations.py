"""
Partie 9.4 -- Slack/Teams/Discord chat-platform integrations. Real,
separate tables per platform (unlike Partie 9.3's own WidgetConfig
consolidation): a Slack `team_id`/bot token, a Teams `tenant_id`/bot
id, and a Discord `guild_id`/bot token are genuinely different real
shapes with genuinely different real fields -- forcing them into one
generic "ChatIntegration" table would mean a dozen nullable,
platform-specific columns on every row. Same real reasoning kept
consistent with the whole project: consolidate when the DATA is
genuinely the same shape (WidgetConfig), keep separate tables when it
genuinely isn't (here).

Every bot/access token below is stored via `encrypt_secret`
(api/security/secret_encryption.py) -- the SAME real Fernet-based
encryption-at-rest this codebase already uses for JWT signing keys and
enterprise SSO client secrets, not a third, separate scheme."""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class SlackIntegration(Base):
    __tablename__ = "slack_integrations"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_slack_integrations_organization_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[str] = mapped_column(String(32))
    team_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bot_token: Mapped[str] = mapped_column(Text)  # encrypted at rest, see this module's own top docstring
    user_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # encrypted at rest
    webhook_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    default_channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SlackMessage(Base):
    __tablename__ = "slack_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    integration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slack_integrations.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    slack_message_ts: Mapped[str] = mapped_column(String(32))
    slack_channel: Mapped[str] = mapped_column(String(64))
    slack_user_id: Mapped[str] = mapped_column(String(32))
    slack_user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    thread_ts: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TeamsIntegration(Base):
    __tablename__ = "teams_integrations"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_teams_integrations_organization_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    team_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bot_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # encrypted at rest
    webhook_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    default_channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TeamsMessage(Base):
    __tablename__ = "teams_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    integration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams_integrations.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    teams_message_id: Mapped[str] = mapped_column(String(128))
    teams_channel: Mapped[str] = mapped_column(String(128))
    teams_user_id: Mapped[str] = mapped_column(String(128))
    teams_user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_to_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DiscordIntegration(Base):
    __tablename__ = "discord_integrations"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_discord_integrations_organization_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    guild_id: Mapped[str] = mapped_column(String(32))
    guild_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bot_token: Mapped[str] = mapped_column(Text)  # encrypted at rest
    bot_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    default_channel_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    default_channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DiscordMessage(Base):
    __tablename__ = "discord_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    integration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discord_integrations.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    discord_message_id: Mapped[str] = mapped_column(String(32))
    discord_channel_id: Mapped[str] = mapped_column(String(32))
    discord_user_id: Mapped[str] = mapped_column(String(32))
    discord_user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_thread: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_message_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
