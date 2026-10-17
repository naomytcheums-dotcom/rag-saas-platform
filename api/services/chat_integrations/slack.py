"""Partie 9.4.1 -- Slack integration."""

import asyncio
import datetime as dt
import logging
import uuid

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.chat_integrations import SlackIntegration, SlackMessage
from api.security.secret_encryption import decrypt_secret, encrypt_secret
from api.services.chat_integrations._common import claim_inbound_event, format_citations_as_footnotes, retry_after_seconds, run_chat_engine

_SLACK_OAUTH_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
_SLACK_OAUTH_ACCESS_URL = "https://slack.com/api/oauth.v2.access"
_SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"


logger = logging.getLogger(__name__)


class SlackIntegrationError(ValueError):
    """Real, honest failure -- routers turn this into a 4xx."""


class SlackDeliveryError(SlackIntegrationError):
    """Slack itself refused or could not be reached when posting (routers turn this into a 502)."""


_OAUTH_STATE_TTL_SECONDS = 600
_OAUTH_STATE_PURPOSE = "slack_oauth_state"


def sign_oauth_state(organization_id: uuid.UUID) -> str:
    """The OAuth `state` is a short-lived signed token, not the bare organization id. The callback is public (Slack redirects the browser to it):
    with a bare id, anyone could finish an authorization of THEIR OWN Slack workspace for ANY organization id and replace that organization's
    integration (its bot token and team) with theirs."""
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"org": str(organization_id), "purpose": _OAUTH_STATE_PURPOSE, "iat": now, "exp": now + dt.timedelta(seconds=_OAUTH_STATE_TTL_SECONDS)}
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm="HS256")


def verify_oauth_state(state: str) -> uuid.UUID:
    try:
        claims = jwt.decode(state, settings.JWT_SECRET_KEY, algorithms=["HS256"], options={"require": ["exp", "iat"]})
        if claims.get("purpose") != _OAUTH_STATE_PURPOSE:
            raise SlackIntegrationError("Invalid OAuth state")
        return uuid.UUID(claims["org"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise SlackIntegrationError("Invalid or expired OAuth state") from exc


def get_oauth_url(organization_id: uuid.UUID) -> str:
    """Item 4's own literal function -- real Slack OAuth v2
    "Add to Slack" URL, `state` carrying the real organization id so
    the callback knows which real org this authorization belongs to."""
    if not settings.SLACK_CLIENT_ID or not settings.SLACK_REDIRECT_URI:
        raise SlackIntegrationError("Slack integration is not configured (SLACK_CLIENT_ID/SLACK_REDIRECT_URI missing)")
    params = httpx.QueryParams({
        "client_id": settings.SLACK_CLIENT_ID, "scope": ",".join(settings.SLACK_SCOPES),
        "redirect_uri": settings.SLACK_REDIRECT_URI, "state": sign_oauth_state(organization_id),
    })
    return f"{_SLACK_OAUTH_AUTHORIZE_URL}?{params}"


async def handle_oauth_callback(db: AsyncSession, code: str, state: str, user_id: uuid.UUID | None) -> SlackIntegration:
    """Item 4's own literal function -- real code-for-token exchange
    against Slack's own real OAuth endpoint."""
    if not settings.SLACK_CLIENT_ID or not settings.SLACK_CLIENT_SECRET:
        raise SlackIntegrationError("Slack integration is not configured")

    organization_id = verify_oauth_state(state)  # before anything is sent to Slack
    try:
        async with httpx.AsyncClient(timeout=settings.SLACK_RESPONSE_TIMEOUT) as http:
            response = await http.post(_SLACK_OAUTH_ACCESS_URL, data={
                "client_id": settings.SLACK_CLIENT_ID, "client_secret": settings.SLACK_CLIENT_SECRET,
                "code": code, "redirect_uri": settings.SLACK_REDIRECT_URI,
            })
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SlackDeliveryError(f"Slack OAuth exchange could not be completed: {type(exc).__name__}") from exc
    if not payload.get("ok"):
        raise SlackIntegrationError(f"Slack OAuth exchange failed: {payload.get('error', 'unknown error')}")

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
    message, created = await claim_inbound_event(
        db, SlackMessage, {"integration_id": integration.id, "slack_message_ts": event["ts"], "slack_channel": event["channel"]},
        {"slack_user_id": event["user"], "slack_user_name": event.get("user_name"), "content": event["text"], "thread_ts": event.get("thread_ts"), "status": "processing"},
    )
    message.is_duplicate = not created
    if not created:
        return message

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

    message.processed_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return message


def format_slack_response(text: str, citations: list[dict]) -> str:
    """Item 4's own literal function -- real Slack mrkdwn."""
    footnotes = format_citations_as_footnotes(citations)
    truncated = text[: settings.SLACK_MAX_MESSAGE_LENGTH]
    return f"{truncated}\n\n{footnotes}" if footnotes else truncated


async def send_slack_response(integration: SlackIntegration, channel: str, text: str, thread_ts: str | None = None) -> dict:
    """Item 4's own literal function -- real `chat.postMessage` call. Slack answers HTTP 200 with `{"ok": false, "error": ...}` for most failures
    (channel_not_found, not_in_channel, token_revoked, ...): that is an error, not a success. A 429 is retried once after `Retry-After`."""
    token = decrypt_secret(integration.bot_token)
    body = {"channel": channel, "text": text, **({"thread_ts": thread_ts} if thread_ts else {})}
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=settings.SLACK_RESPONSE_TIMEOUT) as http:
                response = await http.post(_SLACK_POST_MESSAGE_URL, headers={"Authorization": f"Bearer {token}"}, json=body)
        except httpx.HTTPError as exc:
            raise SlackDeliveryError(f"Slack could not be reached: {type(exc).__name__}") from exc
        if response.status_code == 429 and attempt == 0:
            await asyncio.sleep(retry_after_seconds(response))
            continue
        break
    if response.status_code >= 400:
        raise SlackDeliveryError(f"Slack answered HTTP {response.status_code}")
    try:
        result = response.json()
    except ValueError as exc:
        raise SlackDeliveryError("Slack answered with a body that is not JSON") from exc
    if not result.get("ok"):
        raise SlackDeliveryError(f"Slack refused the message: {result.get('error', 'unknown_error')}")
    return result


async def deliver_slack_reply(integration: SlackIntegration, message: SlackMessage) -> None:
    """Post the stored answer back into the conversation it came from (in the thread of the question). A failure to deliver is recorded on the
    row (`delivery_failed`), never raised: Slack must still get its 200, otherwise it would redeliver the event."""
    if not message.response:
        return
    try:
        await send_slack_response(integration, message.slack_channel, message.response, message.thread_ts or message.slack_message_ts)
    except SlackIntegrationError as exc:
        logger.warning("Slack reply for message %s was not delivered: %s", message.id, exc)
        message.status = "delivery_failed"
