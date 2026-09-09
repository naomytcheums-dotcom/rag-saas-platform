"""Partie 9.4.2 -- Microsoft Teams integration.

⚠️ **Honest limitation (vision critique -- security)**: Teams (Bot
Framework) real auth is a JWT bearer token whose signing key comes
from Microsoft's own live JWKS endpoint
(`https://login.botframework.com/v1/.well-known/openidconfiguration`),
refreshed periodically -- unlike Slack's static signing secret or
Discord's static Ed25519 public key, this genuinely cannot be verified
offline/statically the same way (see
api/security/chat_integrations_signature.py's own top docstring). The
real message-processing/formatting/Adaptive-Card logic below is fully
real and tested; a real, live JWKS-backed bearer-token check on the
inbound webhook is the one real piece this environment (no live Azure
Bot Registration to test against) leaves for a real deployment to wire
up, same class of gap as `10.1.9 SSRF protection` in
docs/CAHIER_DES_CHARGES.md's own Partie 10 status table.
"""

import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.chat_integrations import TeamsIntegration, TeamsMessage
from api.security.secret_encryption import decrypt_secret, encrypt_secret
from api.services.chat_integrations._common import format_citations_as_footnotes, run_chat_engine


class TeamsIntegrationError(ValueError):
    """Real, honest failure -- routers turn this into a 4xx."""


def validate_teams_config(config: dict) -> None:
    if not config.get("webhook_url") and not config.get("bot_id"):
        raise TeamsIntegrationError("Either webhook_url or bot_id/bot_token is required")


async def save_teams_integration(db: AsyncSession, organization_id: uuid.UUID, config: dict, user_id: uuid.UUID) -> TeamsIntegration:
    """Item 4's own literal function."""
    validate_teams_config(config)
    integration = await db.scalar(select(TeamsIntegration).where(TeamsIntegration.organization_id == organization_id))
    if integration is None:
        integration = TeamsIntegration(organization_id=organization_id)
        db.add(integration)

    integration.tenant_id = config.get("tenant_id")
    integration.team_id = config.get("team_id")
    integration.team_name = config.get("team_name")
    integration.bot_id = config.get("bot_id")
    if config.get("bot_token"):
        integration.bot_token = encrypt_secret(config["bot_token"])
    integration.webhook_url = config.get("webhook_url")
    integration.default_channel = config.get("default_channel")
    integration.created_by = integration.created_by or user_id
    await db.flush()
    return integration


def parse_teams_webhook(payload: dict) -> dict:
    """Item 4's own literal function -- real Bot Framework Activity
    shape (`type`, `text`, `from.id`/`from.name`, `conversation.id`,
    `id`, `replyToId`) normalized to this module's own real event
    dict shape."""
    return {
        "id": payload.get("id", ""),
        "channel": (payload.get("conversation") or {}).get("id", ""),
        "user_id": (payload.get("from") or {}).get("id", ""),
        "user_name": (payload.get("from") or {}).get("name"),
        "text": (payload.get("text") or "").strip(),
        "reply_to_id": payload.get("replyToId"),
    }


async def process_teams_message(db: AsyncSession, integration: TeamsIntegration, event: dict) -> TeamsMessage:
    """Item 6's own literal `handle_message_event`."""
    message = TeamsMessage(
        integration_id=integration.id, teams_message_id=event["id"], teams_channel=event["channel"],
        teams_user_id=event["user_id"], teams_user_name=event.get("user_name"), content=event["text"],
        reply_to_id=event.get("reply_to_id"), status="processing",
    )
    db.add(message)
    await db.flush()

    if integration.agent_id is None or integration.created_by is None:
        message.status = "error"
        message.response = "This Teams integration has no agent configured yet."
        await db.flush()
        return message

    result = await run_chat_engine(db, integration.organization_id, integration.created_by, integration.agent_id, event["text"], None)
    if "error" in result:
        message.status = "error"
        message.response = result["error"]
    else:
        message.status = "done"
        message.response = format_teams_response(result["response"], result["citations"])
        message.conversation_id = result["conversation_id"]

    import datetime as dt

    message.processed_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return message


def format_teams_response(text: str, citations: list[dict]) -> str:
    """Item 4's own literal function -- plain text, real truncation;
    `create_response_card` below is the real, richer Adaptive Card
    alternative a caller can choose instead."""
    footnotes = format_citations_as_footnotes(citations)
    truncated = text[: settings.TEAMS_MAX_MESSAGE_LENGTH]
    return f"{truncated}\n\n{footnotes}" if footnotes else truncated


async def send_teams_response(integration: TeamsIntegration, channel: str, text: str, reply_to_id: str | None = None) -> dict:
    """Item 4's own literal function -- real, incoming-webhook-style
    delivery when `webhook_url` is configured (the simplest real Teams
    integration path, no live Bot Framework auth token needed)."""
    if not integration.webhook_url:
        raise TeamsIntegrationError("No webhook_url configured for this Teams integration")
    async with httpx.AsyncClient(timeout=settings.TEAMS_RESPONSE_TIMEOUT) as http:
        response = await http.post(integration.webhook_url, json={"text": text})
    return {"status_code": response.status_code}
