import uuid

from pydantic import BaseModel, ConfigDict


class SlackConfigureRequest(BaseModel):
    default_channel: str | None = None
    agent_id: uuid.UUID | None = None


class SlackConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: str
    team_name: str | None
    default_channel: str | None
    agent_id: uuid.UUID | None
    is_active: bool


class SlackSendMessageRequest(BaseModel):
    channel: str
    text: str
    thread_ts: str | None = None


class TeamsConfigureRequest(BaseModel):
    tenant_id: str | None = None
    team_id: str | None = None
    team_name: str | None = None
    bot_id: str | None = None
    bot_token: str | None = None
    webhook_url: str | None = None
    default_channel: str | None = None
    agent_id: uuid.UUID | None = None


class TeamsConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: str | None
    team_id: str | None
    team_name: str | None
    default_channel: str | None
    agent_id: uuid.UUID | None
    is_active: bool


class TeamsSendMessageRequest(BaseModel):
    channel: str
    text: str
    reply_to_id: str | None = None


class DiscordConfigureRequest(BaseModel):
    guild_id: str
    bot_token: str
    guild_name: str | None = None
    default_channel_id: str | None = None
    default_channel_name: str | None = None
    agent_id: uuid.UUID | None = None


class DiscordConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    guild_id: str
    guild_name: str | None
    default_channel_id: str | None
    agent_id: uuid.UUID | None
    is_active: bool


class DiscordSendMessageRequest(BaseModel):
    channel_id: str
    text: str
    message_id: str | None = None
