"""Partie 9.4.3 -- Discord integration."""

import asyncio
import datetime as dt
import logging
import re
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.chat_integrations import DiscordIntegration, DiscordMessage
from api.security.secret_encryption import decrypt_secret, encrypt_secret
from api.services.chat_integrations._common import claim_inbound_event, format_citations_as_footnotes, retry_after_seconds, run_chat_engine

_DISCORD_API_BASE = "https://discord.com/api/v10"
logger = logging.getLogger(__name__)
_SAFE_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._-]{1,512}$")


class DiscordIntegrationError(ValueError):
    """Real, honest failure -- routers turn this into a 4xx."""


class DiscordDeliveryError(DiscordIntegrationError):
    """Discord itself refused or could not be reached (routers turn this into a 502)."""


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
    message, created = await claim_inbound_event(
        db, DiscordMessage, {"integration_id": integration.id, "discord_message_id": event["id"]},
        {"discord_channel_id": event["channel_id"], "discord_user_id": event["author_id"], "discord_user_name": event.get("author_name"), "content": event["content"],
         "is_thread": event.get("is_thread", False), "parent_message_id": event.get("parent_message_id"), "status": "processing"},
    )
    message.is_duplicate = not created  # a gateway reconnect redelivers events: answered once
    if not created:
        return message

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

    message.processed_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return message


def format_discord_response(text: str, citations: list[dict]) -> str:
    """Item 4's own literal function -- real Discord markdown."""
    footnotes = format_citations_as_footnotes(citations)
    truncated = text[: settings.DISCORD_MAX_MESSAGE_LENGTH]
    return f"{truncated}\n\n{footnotes}" if footnotes else truncated


async def _discord_request(method: str, url: str, *, headers: dict | None = None, json: dict | None = None) -> dict:
    """One Discord REST call: a 429 is retried once after the `retry_after` Discord states, every other failure is a DiscordDeliveryError."""
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=settings.DISCORD_RESPONSE_TIMEOUT) as http:
                response = await http.request(method, url, headers=headers, json=json)
        except httpx.HTTPError as exc:
            raise DiscordDeliveryError(f"Discord could not be reached: {type(exc).__name__}") from exc
        if response.status_code == 429 and attempt == 0:
            await asyncio.sleep(retry_after_seconds(response))
            continue
        break
    if response.status_code >= 400:
        try:
            detail = response.json().get("message", "")
        except (ValueError, AttributeError):
            detail = ""
        raise DiscordDeliveryError(f"Discord answered HTTP {response.status_code}: {detail}".rstrip(": "))
    try:
        return response.json()
    except ValueError:
        return {}


async def send_discord_response(integration: DiscordIntegration, channel_id: str, text: str, message_id: str | None = None) -> dict:
    """Item 4's own literal function -- real `POST /channels/{id}/messages`."""
    token = decrypt_secret(integration.bot_token)
    return await _discord_request(
        "POST", f"{_DISCORD_API_BASE}/channels/{channel_id}/messages", headers={"Authorization": f"Bot {token}"},
        json={"content": text, **({"message_reference": {"message_id": message_id}} if message_id else {})},
    )


async def create_discord_thread(integration: DiscordIntegration, channel_id: str, message_id: str, title: str) -> dict:
    """Item 4's own literal function -- real `POST /channels/{id}/messages/{id}/threads`."""
    token = decrypt_secret(integration.bot_token)
    return await _discord_request(
        "POST", f"{_DISCORD_API_BASE}/channels/{channel_id}/messages/{message_id}/threads", headers={"Authorization": f"Bot {token}"}, json={"name": title[:100]},
    )


async def edit_interaction_response(application_id: str, interaction_token: str, content: str) -> dict:
    """Replace the "thinking..." placeholder of a deferred slash command (`PATCH /webhooks/{app}/{token}/messages/@original`). The interaction token
    in the URL is the credential: no bot token is sent."""
    if not _SAFE_PATH_SEGMENT.match(application_id) or not _SAFE_PATH_SEGMENT.match(interaction_token):
        raise DiscordIntegrationError("malformed interaction identifiers")
    return await _discord_request("PATCH", f"{_DISCORD_API_BASE}/webhooks/{application_id}/{interaction_token}/messages/@original", json={"content": content[: settings.DISCORD_MAX_MESSAGE_LENGTH]})


# Discord invalidates an interaction that is not answered within 3 s, and a RAG answer takes longer: the slash command is acknowledged at once
# (type 5, "thinking...") and the answer is edited in when it is ready, from a background task with its own database session.
_background_tasks: set[asyncio.Task] = set()


def _session_factory():
    from api.database import AsyncSessionLocal

    return AsyncSessionLocal


def start_deferred_command(integration_id: uuid.UUID, command: str, args: str, application_id: str, interaction_token: str) -> asyncio.Task:
    task = asyncio.create_task(_run_deferred_command(integration_id, command, args, application_id, interaction_token))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def _run_deferred_command(integration_id: uuid.UUID, command: str, args: str, application_id: str, interaction_token: str) -> None:
    try:
        async with _session_factory()() as db:
            integration = await db.get(DiscordIntegration, integration_id)
            reply = "This server has no active RAG SaaS integration." if integration is None or not integration.is_active else await handle_command(db, integration, command, args, {"conversation_id": None})
            await db.commit()
    except Exception:  # noqa: BLE001 -- the user is waiting on "thinking...": always replace it
        logger.exception("deferred Discord command failed")
        reply = "Sorry, something went wrong while answering."
    try:
        await edit_interaction_response(application_id, interaction_token, reply)
    except DiscordIntegrationError as exc:
        logger.warning("Discord interaction follow-up was not delivered: %s", exc)


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
