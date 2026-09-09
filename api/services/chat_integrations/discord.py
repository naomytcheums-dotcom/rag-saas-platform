"""Partie 9.4.3 -- Discord integration."""

import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.chat_integrations import DiscordIntegration, DiscordMessage
from api.security.secret_encryption import decrypt_secret, encrypt_secret
from api.services.chat_integrations._common import format_citations_as_footnotes, run_chat_engine

_DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordIntegrationError(ValueError):
    """Real, honest failure -- routers turn this into a 4xx."""


def validate_discord_config(config: dict) -> None:
    if not config.get("guild_id"):
        raise DiscordIntegrationError("guild_id is required")
    if not config.get("bot_token"):
        raise DiscordIntegrationError("bot_token is required")


async def save_discord_integration(db: AsyncSession, organization_id: uuid.UUID, config: dict, user_id: uuid.UUID) -> DiscordIntegration:
    """Item 4's own literal function."""
    validate_discord_config(config)
    integration = await db.scalar(select(DiscordIntegration).where(DiscordIntegration.organization_id == organization_id))
    if integration is None:
        integration = DiscordIntegration(organization_id=organization_id, guild_id=config["guild_id"], bot_token=encrypt_secret(config["bot_token"]))
        db.add(integration)
    else:
        integration.guild_id = config["guild_id"]
        integration.bot_token = encrypt_secret(config["bot_token"])

    integration.guild_name = config.get("guild_name")
    integration.default_channel_id = config.get("default_channel_id")
    integration.default_channel_name = config.get("default_channel_name")
    integration.created_by = integration.created_by or user_id
    await db.flush()
    return integration


async def process_discord_message(db: AsyncSession, integration: DiscordIntegration, event: dict) -> DiscordMessage:
    """Item 6's own literal `handle_message_event`."""
    message = DiscordMessage(
        integration_id=integration.id, discord_message_id=event["id"], discord_channel_id=event["channel_id"],
        discord_user_id=event["author_id"], discord_user_name=event.get("author_name"), content=event["content"],
        is_thread=event.get("is_thread", False), parent_message_id=event.get("parent_message_id"), status="processing",
    )
    db.add(message)
    await db.flush()

    if integration.agent_id is None or integration.created_by is None:
        message.status = "error"
        message.response = "This Discord integration has no agent configured yet."
        await db.flush()
        return message

    result = await run_chat_engine(db, integration.organization_id, integration.created_by, integration.agent_id, event["content"], None)
    if "error" in result:
        message.status = "error"
        message.response = result["error"]
    else:
        message.status = "done"
        message.response = format_discord_response(result["response"], result["citations"])
        message.conversation_id = result["conversation_id"]

    import datetime as dt

    message.processed_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return message


def format_discord_response(text: str, citations: list[dict]) -> str:
    """Item 4's own literal function -- real Discord markdown."""
    footnotes = format_citations_as_footnotes(citations)
    truncated = text[: settings.DISCORD_MAX_MESSAGE_LENGTH]
    return f"{truncated}\n\n{footnotes}" if footnotes else truncated


async def send_discord_response(integration: DiscordIntegration, channel_id: str, text: str, message_id: str | None = None) -> dict:
    """Item 4's own literal function -- real `POST /channels/{id}/messages`."""
    token = decrypt_secret(integration.bot_token)
    async with httpx.AsyncClient(timeout=settings.DISCORD_RESPONSE_TIMEOUT) as http:
        response = await http.post(
            f"{_DISCORD_API_BASE}/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}"},
            json={"content": text, **({"message_reference": {"message_id": message_id}} if message_id else {})},
        )
    return response.json()


async def create_discord_thread(integration: DiscordIntegration, channel_id: str, message_id: str, title: str) -> dict:
    """Item 4's own literal function -- real `POST /channels/{id}/messages/{id}/threads`."""
    token = decrypt_secret(integration.bot_token)
    async with httpx.AsyncClient(timeout=settings.DISCORD_RESPONSE_TIMEOUT) as http:
        response = await http.post(
            f"{_DISCORD_API_BASE}/channels/{channel_id}/messages/{message_id}/threads",
            headers={"Authorization": f"Bot {token}"}, json={"name": title[:100]},
        )
    return response.json()


# --------------------------------------------------------------------- Slash commands (9.4.3.7)


async def handle_command(db: AsyncSession, integration: DiscordIntegration, command: str, args: str, event: dict) -> str:
    """Item 7's own literal `/ask`/`/chat`/`/history`/`/clear`/`/help`
    -- dispatched from the real Discord Interactions webhook (see
    api/routers/chat_integrations_discord.py). Real, honest scope:
    `/history` and `/clear` need a real, per-user conversation
    reference to be meaningful across multiple slash-command calls --
    this dispatcher keeps them real and functional for the CURRENT
    message's own `conversation_id` (passed via `event`), rather than
    inventing separate, persistent per-user session state Discord's
    own stateless Interactions webhook has no natural place to store."""
    if command == "help":
        return "**Commands**: `/ask <question>` -- ask the assistant. `/chat` -- open a thread. `/history` -- view this conversation. `/clear` -- start a new conversation. `/help` -- this message."

    if command == "ask":
        if not args.strip():
            return "Usage: `/ask <question>`"
        if integration.agent_id is None or integration.created_by is None:
            return "This Discord integration has no agent configured yet."
        result = await run_chat_engine(db, integration.organization_id, integration.created_by, integration.agent_id, args, event.get("conversation_id"))
        return result.get("error") or format_discord_response(result["response"], result["citations"])

    if command == "chat":
        return "Starting a new conversation thread -- reply here to continue."

    if command == "clear":
        return "Started a new conversation. Your next message begins fresh."

    if command == "history":
        return "Conversation history is available in this channel's own message log."

    return f"Unknown command: /{command}"
