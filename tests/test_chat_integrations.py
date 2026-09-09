"""Partie 9.4.1 (Slack) + 9.4.2 (Teams) + 9.4.3 (Discord)."""

import hashlib
import hmac
import time
import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from litellm.types.utils import Choices, Message, ModelResponse
from sqlalchemy import select

from api.config import settings
from api.models.agent import Agent
from api.models.chat_integrations import DiscordIntegration, SlackIntegration, TeamsIntegration
from api.security.chat_integrations_signature import verify_discord_signature, verify_slack_signature
from api.security.secret_encryption import decrypt_secret
from api.services.chat_integrations.cards import create_error_card, create_response_card
from api.services.chat_integrations.discord import format_discord_response, handle_command, save_discord_integration
from api.services.chat_integrations.slack import format_slack_response, save_integration
from api.services.chat_integrations.teams import format_teams_response, parse_teams_webhook, save_teams_integration


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _make_org(client, db_session, register_payload):
    from api.models.user import User

    payload = {"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True}
    token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Integrations Org"}, headers=_auth_header(token))).json()["id"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    return token, org_id, user.id


async def _make_agent(db_session, org_id: str) -> str:
    agent = Agent(organization_id=uuid.UUID(org_id), name="Integration Agent", system_prompt="You are helpful.", idk_threshold=0.0)
    db_session.add(agent)
    await db_session.flush()
    await db_session.commit()
    return str(agent.id)


# ------------------------------------------------------------------- 9.4.1 Slack


async def test_slack_permissions(client, db_session, register_payload):
    """Validation criterion: test_slack_permissions -- les permissions
    sont respectées (a member with no integration configured gets 404,
    never a leaked cross-org row)."""
    token, org_id, _user_id = await _make_org(client, db_session, register_payload)
    response = await client.get(f"/organizations/{org_id}/integrations/slack/config", headers=_auth_header(token))
    assert response.status_code == 404


async def test_slack_oauth_flow_saves_encrypted_tokens(db_session):
    """Validation criterion: test_slack_oauth_flow."""
    org_id = uuid.uuid4()
    integration = await save_integration(db_session, org_id, {"team_id": "T123", "team_name": "Test Team", "bot_token": "xoxb-real-token"}, None)
    await db_session.commit()

    assert integration.bot_token != "xoxb-real-token"
    assert decrypt_secret(integration.bot_token) == "xoxb-real-token"


async def test_slack_message_processing(client, db_session, register_payload, monkeypatch):
    """Validation criterion: test_slack_message_processing."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Hello from Slack!")))
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[]))

    from api.services.chat_integrations.slack import process_slack_message

    _token, org_id, user_id = await _make_org(client, db_session, register_payload)
    agent_id = await _make_agent(db_session, org_id)
    integration = await save_integration(db_session, uuid.UUID(org_id), {"team_id": "T1", "bot_token": "xoxb-x"}, user_id)
    integration.agent_id = uuid.UUID(agent_id)
    await db_session.commit()

    message = await process_slack_message(db_session, integration, {"ts": "123.456", "channel": "C1", "user": "U1", "text": "Hi there"})
    await db_session.commit()

    assert message.status == "done"
    assert "Hello from Slack!" in message.response


def test_slack_response_formatting_includes_citations():
    """Validation criterion: test_slack_response_formatting."""
    formatted = format_slack_response("The answer is 42.", [{"citation_number": 1, "source_title": "Docs"}])
    assert "The answer is 42." in formatted
    assert "[1] Docs" in formatted


async def test_slack_webhook_verifies_signature(client):
    """Validation criterion: test_slack_webhook."""
    response = await client.post("/integrations/slack/events", json={"type": "url_verification", "challenge": "abc"})
    assert response.status_code == 403  # unsigned request is rejected


def test_verify_slack_signature_accepts_a_real_computed_signature(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", "test-signing-secret")
    timestamp = str(int(time.time()))
    body = b'{"type":"url_verification","challenge":"abc"}'
    basestring = f"v0:{timestamp}:{body.decode()}".encode()
    signature = "v0=" + hmac.new(b"test-signing-secret", basestring, hashlib.sha256).hexdigest()

    assert verify_slack_signature(timestamp, body, signature) is True


def test_verify_slack_signature_rejects_wrong_signature(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", "test-signing-secret")
    assert verify_slack_signature(str(int(time.time())), b"{}", "v0=wrong") is False


def test_verify_slack_signature_rejects_old_timestamp(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", "test-signing-secret")
    old_timestamp = str(int(time.time()) - 1000)
    body = b"{}"
    basestring = f"v0:{old_timestamp}:{body.decode()}".encode()
    signature = "v0=" + hmac.new(b"test-signing-secret", basestring, hashlib.sha256).hexdigest()
    assert verify_slack_signature(old_timestamp, body, signature) is False


# ------------------------------------------------------------------- 9.4.2 Teams


def test_teams_configuration_requires_webhook_or_bot():
    from api.services.chat_integrations.teams import TeamsIntegrationError, validate_teams_config

    with pytest.raises(TeamsIntegrationError):
        validate_teams_config({})


def test_parse_teams_webhook_normalizes_activity_shape():
    """Validation criterion: test_teams_configuration."""
    activity = {"id": "msg1", "conversation": {"id": "conv1"}, "from": {"id": "u1", "name": "Ada"}, "text": " Hello "}
    parsed = parse_teams_webhook(activity)
    assert parsed == {"id": "msg1", "channel": "conv1", "user_id": "u1", "user_name": "Ada", "text": "Hello", "reply_to_id": None}


async def test_teams_message_processing(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Hello from Teams!")))
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[]))

    from api.services.chat_integrations.teams import process_teams_message

    _token, org_id, user_id = await _make_org(client, db_session, register_payload)
    agent_id = await _make_agent(db_session, org_id)
    integration = await save_teams_integration(db_session, uuid.UUID(org_id), {"webhook_url": "https://example.invalid/webhook"}, user_id)
    integration.agent_id = uuid.UUID(agent_id)
    await db_session.commit()

    message = await process_teams_message(db_session, integration, {"id": "m1", "channel": "c1", "user_id": "u1", "text": "Hi"})
    await db_session.commit()

    assert message.status == "done"
    assert "Hello from Teams!" in message.response


def test_teams_response_formatting():
    """Validation criterion: test_teams_response_formatting."""
    assert format_teams_response("Answer", []) == "Answer"


def test_teams_adaptive_cards_are_generated():
    """Validation criterion: test_teams_adaptive_cards."""
    card = create_response_card("The answer is 42.", [{"citation_number": 1, "source_title": "Docs"}])
    assert card["type"] == "AdaptiveCard"
    assert card["body"][1]["type"] == "FactSet"

    error_card = create_error_card("Something went wrong")
    assert "Something went wrong" in error_card["body"][0]["text"]


async def test_teams_permissions(client, db_session, register_payload):
    """Validation criterion: test_teams_permissions."""
    token, org_id, _user_id = await _make_org(client, db_session, register_payload)
    response = await client.get(f"/organizations/{org_id}/integrations/teams/config", headers=_auth_header(token))
    assert response.status_code == 404


# ------------------------------------------------------------------- 9.4.3 Discord


async def test_discord_configuration(client, db_session, register_payload):
    """Validation criterion: test_discord_configuration."""
    token, org_id, _user_id = await _make_org(client, db_session, register_payload)
    response = await client.post(
        f"/organizations/{org_id}/integrations/discord/configure",
        json={"guild_id": "G1", "bot_token": "real-bot-token", "guild_name": "My Server"},
        headers=_auth_header(token),
    )
    assert response.status_code == 200
    assert response.json()["guild_id"] == "G1"

    stored = await db_session.scalar(select(DiscordIntegration).where(DiscordIntegration.organization_id == uuid.UUID(org_id)))
    assert decrypt_secret(stored.bot_token) == "real-bot-token"


async def test_discord_message_processing(client, db_session, register_payload, monkeypatch):
    """Validation criterion: test_discord_message_processing."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Hello from Discord!")))
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[]))

    from api.services.chat_integrations.discord import process_discord_message

    _token, org_id, user_id = await _make_org(client, db_session, register_payload)
    agent_id = await _make_agent(db_session, org_id)
    integration = await save_discord_integration(db_session, uuid.UUID(org_id), {"guild_id": "G1", "bot_token": "tok"}, user_id)
    integration.agent_id = uuid.UUID(agent_id)
    await db_session.commit()

    message = await process_discord_message(db_session, integration, {"id": "m1", "channel_id": "c1", "author_id": "u1", "content": "Hi"})
    await db_session.commit()

    assert message.status == "done"
    assert "Hello from Discord!" in message.response


def test_discord_response_formatting():
    """Validation criterion: test_discord_response_formatting."""
    assert format_discord_response("Answer", []) == "Answer"


async def test_discord_commands_ask(client, db_session, register_payload, monkeypatch):
    """Validation criterion: test_discord_commands."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("42")))
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[]))

    _token, org_id, user_id = await _make_org(client, db_session, register_payload)
    agent_id = await _make_agent(db_session, org_id)
    integration = await save_discord_integration(db_session, uuid.UUID(org_id), {"guild_id": "G1", "bot_token": "tok"}, user_id)
    integration.agent_id = uuid.UUID(agent_id)
    await db_session.commit()

    reply = await handle_command(db_session, integration, "ask", "What is the answer?", {})
    await db_session.commit()
    assert "42" in reply

    help_reply = await handle_command(db_session, integration, "help", "", {})
    assert "/ask" in help_reply

    empty_ask = await handle_command(db_session, integration, "ask", "  ", {})
    assert "Usage" in empty_ask


async def test_discord_permissions(client, db_session, register_payload):
    """Validation criterion: test_discord_permissions."""
    token, org_id, _user_id = await _make_org(client, db_session, register_payload)
    response = await client.get(f"/organizations/{org_id}/integrations/discord/config", headers=_auth_header(token))
    assert response.status_code == 404


def test_verify_discord_signature_accepts_a_real_ed25519_signature(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    public_key_hex = private_key.public_key().public_bytes_raw().hex()
    monkeypatch.setattr(settings, "DISCORD_PUBLIC_KEY", public_key_hex)

    timestamp = "1700000000"
    body = b'{"type":1}'
    signature = private_key.sign(timestamp.encode() + body).hex()

    assert verify_discord_signature(timestamp, body, signature) is True


def test_verify_discord_signature_rejects_tampered_body(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(settings, "DISCORD_PUBLIC_KEY", private_key.public_key().public_bytes_raw().hex())

    timestamp = "1700000000"
    signature = private_key.sign(timestamp.encode() + b'{"type":1}').hex()

    assert verify_discord_signature(timestamp, b'{"type":2}', signature) is False


async def test_discord_interactions_ping(client, monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(settings, "DISCORD_PUBLIC_KEY", private_key.public_key().public_bytes_raw().hex())

    timestamp = "1700000000"
    body = b'{"type":1}'
    signature = private_key.sign(timestamp.encode() + body).hex()

    response = await client.post(
        "/integrations/discord/interactions", content=body,
        headers={"Content-Type": "application/json", "X-Signature-Ed25519": signature, "X-Signature-Timestamp": timestamp},
    )
    assert response.status_code == 200
    assert response.json() == {"type": 1}


async def test_discord_interactions_rejects_invalid_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "DISCORD_PUBLIC_KEY", Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex())
    response = await client.post(
        "/integrations/discord/interactions", json={"type": 1},
        headers={"X-Signature-Ed25519": "00" * 64, "X-Signature-Timestamp": "1700000000"},
    )
    assert response.status_code == 401


# ------------------------------------------------------------------- Cross-org isolation


async def test_chat_integrations_cross_org_isolation(client, db_session, register_payload):
    token_a, org_a, _user_a = await _make_org(client, db_session, register_payload)
    other_payload = dict(register_payload, email="other-" + register_payload["email"])
    token_b, org_b, _user_b = await _make_org(client, db_session, other_payload)

    await save_discord_integration(db_session, uuid.UUID(org_a), {"guild_id": "G1", "bot_token": "tok"}, uuid.uuid4())
    await db_session.commit()

    response = await client.get(f"/organizations/{org_a}/integrations/discord/config", headers=_auth_header(token_b))
    assert response.status_code == 404  # not a member of org_a at all -- anti-enumeration, same as require_org_member
