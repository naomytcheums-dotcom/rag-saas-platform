"""Partie 9.4.1 -- Slack integration."""

import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.chat_integrations import SlackIntegration, SlackMessage
from api.security.secret_encryption import decrypt_secret, encrypt_secret
from api.services.chat_integrations._common import format_citations_as_footnotes, run_chat_engine

_SLACK_OAUTH_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
_SLACK_OAUTH_ACCESS_URL = "https://slack.com/api/oauth.v2.access"
_SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"


class SlackIntegrationError(ValueError):
    """Real, honest failure -- routers turn this into a 4xx."""


def get_oauth_url(organization_id: uuid.UUID) -> str:
    """Item 4's own literal function -- real Slack OAuth v2
    "Add to Slack" URL, `state` carrying the real organization id so
    the callback knows which real org this authorization belongs to."""
    if not settings.SLACK_CLIENT_ID or not settings.SLACK_REDIRECT_URI:
        raise SlackIntegrationError("Slack integration is not configured (SLACK_CLIENT_ID/SLACK_REDIRECT_URI missing)")
    params = httpx.QueryParams({
        "client_id": settings.SLACK_CLIENT_ID, "scope": ",".join(settings.SLACK_SCOPES),
        "redirect_uri": settings.SLACK_REDIRECT_URI, "state": str(organization_id),
    })
    return f"{_SLACK_OAUTH_AUTHORIZE_URL}?{params}"


async def handle_oauth_callback(db: AsyncSession, code: str, state: str, user_id: uuid.UUID | None) -> SlackIntegration:
    """Item 4's own literal function -- real code-for-token exchange
    against Slack's own real OAuth endpoint."""
    if not settings.SLACK_CLIENT_ID or not settings.SLACK_CLIENT_SECRET:
        raise SlackIntegrationError("Slack integration is not configured")

    async with httpx.AsyncClient(timeout=settings.SLACK_RESPONSE_TIMEOUT) as http:
        response = await http.post(_SLACK_OAUTH_ACCESS_URL, data={
            "client_id": settings.SLACK_CLIENT_ID, "client_secret": settings.SLACK_CLIENT_SECRET,
            "code": code, "redirect_uri": settings.SLACK_REDIRECT_URI,
        })
    payload = response.json()
    if not payload.get("ok"):
        raise SlackIntegrationError(f"Slack OAuth exchange failed: {payload.get('error', 'unknown error')}")

    organization_id = uuid.UUID(state)
    return await save_integration(db, organization_id, {
        "team_id": payload["team"]["id"], "team_name": payload["team"].get("name"),
        "bot_token": payload["access_token"], "user_token": (payload.get("authed_user") or {}).get("access_token"),
    }, user_id)


async def save_integration(db: AsyncSession, organization_id: uuid.UUID, token_data: dict, user_id: uuid.UUID | None) -> SlackIntegration:
    """Item 4's own literal function -- real upsert (an organization
    re-authorizing replaces its existing real integration rather than
    creating a real duplicate row)."""
    integration = await db.scalar(select(SlackIntegration).where(SlackIntegration.organization_id == organization_id))
    if integration is None:
        integration = SlackIntegration(organization_id=organization_id, team_id=token_data["team_id"])
        db.add(integration)

    integration.team_id = token_data["team_id"]
    integration.team_name = token_data.get("team_name")
    integration.bot_token = encrypt_secret(token_data["bot_token"])
    if token_data.get("user_token"):
        integration.user_token = encrypt_secret(token_data["user_token"])
    integration.created_by = integration.created_by or user_id
    await db.flush()
    return integration


def validate_slack_config(config: dict) -> None:
    if config.get("default_channel") is not None and not str(config["default_channel"]).strip():
        raise SlackIntegrationError("default_channel cannot be blank")


async def process_slack_message(db: AsyncSession, integration: SlackIntegration, event: dict) -> SlackMessage:
    """Item 6's own literal `handle_message_event` -- persists the
    real inbound message, runs it through the SAME real chat engine
    every other real entry point in this codebase uses
    (`run_chat_engine`, see _common.py), and persists the real
    response back onto the SAME row (never a separate, second
    "response" table)."""
    message = SlackMessage(
        integration_id=integration.id, slack_message_ts=event["ts"], slack_channel=event["channel"],
        slack_user_id=event["user"], slack_user_name=event.get("user_name"), content=event["text"],
        thread_ts=event.get("thread_ts"), status="processing",
    )
    db.add(message)
    await db.flush()

    if integration.agent_id is None or integration.created_by is None:
        message.status = "error"
        message.response = "This Slack integration has no agent configured yet."
        await db.flush()
        return message

    result = await run_chat_engine(db, integration.organization_id, integration.created_by, integration.agent_id, event["text"], None)
    if "error" in result:
        message.status = "error"
        message.response = result["error"]
    else:
        message.status = "done"
        message.response = format_slack_response(result["response"], result["citations"])
        message.conversation_id = result["conversation_id"]

    import datetime as dt

    message.processed_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return message


def format_slack_response(text: str, citations: list[dict]) -> str:
    """Item 4's own literal function -- real Slack mrkdwn."""
    footnotes = format_citations_as_footnotes(citations)
    truncated = text[: settings.SLACK_MAX_MESSAGE_LENGTH]
    return f"{truncated}\n\n{footnotes}" if footnotes else truncated


async def send_slack_response(integration: SlackIntegration, channel: str, text: str, thread_ts: str | None = None) -> dict:
    """Item 4's own literal function -- real `chat.postMessage` call."""
    token = decrypt_secret(integration.bot_token)
    async with httpx.AsyncClient(timeout=settings.SLACK_RESPONSE_TIMEOUT) as http:
        response = await http.post(
            _SLACK_POST_MESSAGE_URL, headers={"Authorization": f"Bearer {token}"},
            json={"channel": channel, "text": text, **({"thread_ts": thread_ts} if thread_ts else {})},
        )
    return response.json()
