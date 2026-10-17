"""Specs 9.4.1 Slack, 9.4.2 Microsoft Teams, 9.4.3 Discord -- CONTRACT tests against LOCAL FAKE platforms.

Real: the product's webhook endpoints, signature/JWT verification, idempotent intake, reply delivery code and the HTTP client, over real loopback sockets
(HTTPS with a self-signed certificate for the Bot Framework connector). Fake: Slack's Web API, Discord's REST API and Microsoft's token endpoint and
connector -- they speak the documented wire format, they are NOT the services. The LLM answer is a stub (covered by test_llm_vendor_contract.py).
Real validation needs a Slack app, a Discord application and an Azure Bot registration: see docs/project-handover/e2e_evidence/external_RESUME.md.
"""

import asyncio
import hashlib
import hmac
import json
import time
import uuid

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.config import settings
from api.models.chat_integrations import DiscordIntegration, DiscordMessage, SlackIntegration, SlackMessage, TeamsIntegration, TeamsMessage
from api.security import teams_bot_auth
from api.services.chat_integrations import discord as discord_service
from api.services.chat_integrations import slack as slack_service
from api.services.chat_integrations import teams as teams_service
from api.services.chat_integrations.discord import save_discord_integration
from api.services.chat_integrations.slack import save_integration
from api.services.chat_integrations.teams import save_teams_integration
from test_chat_integrations import _make_agent, _make_org
from vendor_fakes import FakeVendor, Resp, closed_url

SIGNING_SECRET = "slack-contract-signing-secret"


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", SIGNING_SECRET)
    monkeypatch.setattr(settings, "SLACK_CLIENT_ID", "slack-client")
    monkeypatch.setattr(settings, "SLACK_CLIENT_SECRET", "slack-client-secret")
    monkeypatch.setattr(settings, "SLACK_REDIRECT_URI", "https://app.example.test/integrations/slack/callback")

    async def instant(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", instant)


class Engine:
    """Stands in for the RAG chat engine; counts how many times a question was really answered."""

    def __init__(self, monkeypatch, *modules):
        self.questions: list[str] = []
        for module in modules:
            monkeypatch.setattr(module, "run_chat_engine", self.run)

    async def run(self, db, organization_id, created_by, agent_id, message, conversation_id):
        self.questions.append(message)
        return {"response": f"Answer to: {message}", "citations": [], "conversation_id": None}


# ---------------------------------------------------------------------------------------------------------------------------------- Slack


def slack_headers(body: bytes, secret: str = SIGNING_SECRET, timestamp: int | None = None, retry: int | None = None) -> dict:
    stamp = str(int(time.time()) if timestamp is None else timestamp)
    signature = "v0=" + hmac.new(secret.encode(), f"v0:{stamp}:".encode() + body, hashlib.sha256).hexdigest()
    headers = {"X-Slack-Signature": signature, "X-Slack-Request-Timestamp": stamp, "Content-Type": "application/json"}
    if retry is not None:
        headers["X-Slack-Retry-Num"] = str(retry)
    return headers


def event_payload(ts="1700000000.000100", text="<@UBOT> what is RAG?", etype="app_mention", **extra) -> bytes:
    event = {"type": etype, "user": "U1", "text": text, "ts": ts, "channel": "C1", **extra}
    return json.dumps({"type": "event_callback", "team_id": "T1", "event_id": f"Ev{ts}", "event": event}).encode()


@pytest.fixture
async def slack_env(client, db_session, register_payload, monkeypatch):
    with FakeVendor() as slack:
        monkeypatch.setattr(slack_service, "_SLACK_POST_MESSAGE_URL", f"{slack.url}/api/chat.postMessage")
        monkeypatch.setattr(slack_service, "_SLACK_OAUTH_ACCESS_URL", f"{slack.url}/api/oauth.v2.access")
        slack.on("POST", "/api/chat.postMessage", Resp(200, {"ok": True, "ts": "1700000001.000200"}))
        _token, org_id, user_id = await _make_org(client, db_session, register_payload)
        agent_id = await _make_agent(db_session, org_id)
        integration = await save_integration(db_session, uuid.UUID(org_id), {"team_id": "T1", "bot_token": "xoxb-contract-token"}, user_id)
        integration.agent_id = uuid.UUID(agent_id)
        await db_session.commit()
        engine = Engine(monkeypatch, slack_service)
        yield type("SlackEnv", (), {"client": client, "db": db_session, "fake": slack, "org_id": org_id, "engine": engine, "integration": integration})


async def post_event(env, body: bytes, **kw):
    return await env.client.post("/integrations/slack/events", content=body, headers=slack_headers(body, **kw))


async def test_slack_url_verification_handshake(slack_env):
    body = json.dumps({"type": "url_verification", "challenge": "abc123"}).encode()
    response = await post_event(slack_env, body)
    assert response.status_code == 200 and response.json() == {"challenge": "abc123"}


async def test_slack_mention_is_answered_in_the_thread_of_the_question(slack_env):
    response = await post_event(slack_env, event_payload())
    assert response.status_code == 200
    assert slack_env.engine.questions == ["what is RAG?"]  # the "<@UBOT>" mention is not part of the question
    (post,) = slack_env.fake.calls("POST", "/api/chat.postMessage")
    assert post.headers["authorization"] == "Bearer xoxb-contract-token"
    assert post.json() == {"channel": "C1", "text": "Answer to: what is RAG?", "thread_ts": "1700000000.000100"}
    row = await slack_env.db.scalar(select(SlackMessage))
    assert row.status == "done" and row.response == "Answer to: what is RAG?"


async def test_slack_retry_of_the_same_event_is_acknowledged_but_not_answered_twice(slack_env):
    assert (await post_event(slack_env, event_payload())).status_code == 200
    assert (await post_event(slack_env, event_payload(), retry=1)).status_code == 200  # Slack redelivers when the 3 s ack was missed
    assert (await post_event(slack_env, event_payload(), retry=2)).status_code == 200
    assert len(slack_env.engine.questions) == 1 and len(slack_env.fake.calls("POST", "/api/chat.postMessage")) == 1


async def test_slack_message_and_app_mention_twins_are_answered_once(slack_env):
    await post_event(slack_env, event_payload(etype="app_mention"))
    await post_event(slack_env, event_payload(etype="message"))  # Slack sends BOTH events for one @mention in a channel
    assert len(slack_env.engine.questions) == 1


@pytest.mark.parametrize("extra", [{"bot_id": "B1"}, {"subtype": "message_changed"}, {"subtype": "bot_message"}, {"text": "<@UBOT>"}, {"text": "   "}])
async def test_slack_events_that_are_not_user_questions_are_ignored(slack_env, extra):
    body = event_payload(ts="1700000009.000900", **extra)
    assert (await post_event(slack_env, body)).status_code == 200
    assert slack_env.engine.questions == [] and slack_env.fake.calls("POST", "/api/chat.postMessage") == []


async def test_slack_refusing_the_reply_is_recorded_and_the_webhook_still_answers_200(slack_env):
    slack_env.fake.on("POST", "/api/chat.postMessage", Resp(200, {"ok": False, "error": "channel_not_found"}))
    slack_env.fake._routes.pop(0)  # the fixture's default route comes first: drop it so this one answers
    response = await post_event(slack_env, event_payload(ts="1700000020.000100"))
    assert response.status_code == 200  # a non-200 would make Slack redeliver the event
    assert (await slack_env.db.scalar(select(SlackMessage).where(SlackMessage.slack_message_ts == "1700000020.000100"))).status == "delivery_failed"


async def test_slack_down_is_recorded_and_the_webhook_still_answers_200(slack_env, monkeypatch):
    monkeypatch.setattr(slack_service, "_SLACK_POST_MESSAGE_URL", f"{closed_url()}/api/chat.postMessage")
    response = await post_event(slack_env, event_payload(ts="1700000030.000100"))
    assert response.status_code == 200
    assert (await slack_env.db.scalar(select(SlackMessage).where(SlackMessage.slack_message_ts == "1700000030.000100"))).status == "delivery_failed"


async def test_slack_rate_limited_reply_is_retried_once(slack_env):
    slack_env.fake._routes.clear()
    slack_env.fake.on("POST", "/api/chat.postMessage", [Resp(429, {"ok": False, "error": "ratelimited"}, headers={"Retry-After": "1"}), Resp(200, {"ok": True})])
    await post_event(slack_env, event_payload(ts="1700000040.000100"))
    assert len(slack_env.fake.calls("POST", "/api/chat.postMessage")) == 2
    assert (await slack_env.db.scalar(select(SlackMessage).where(SlackMessage.slack_message_ts == "1700000040.000100"))).status == "done"


async def test_slack_signature_failures_are_refused_and_nothing_is_processed(slack_env):
    body = event_payload()
    bad_secret = await post_event(slack_env, body, secret="not-the-secret")
    stale = await post_event(slack_env, body, timestamp=int(time.time()) - 1000)
    unsigned = await slack_env.client.post("/integrations/slack/events", content=body, headers={"Content-Type": "application/json"})
    not_utf8 = b"\xff\xfe{}"
    garbled = await slack_env.client.post("/integrations/slack/events", content=not_utf8, headers=slack_headers(not_utf8, secret="x"))
    assert [r.status_code for r in (bad_secret, stale, unsigned, garbled)] == [403, 403, 403, 403]  # a body that is not UTF-8 used to be a 500
    assert slack_env.engine.questions == []


async def test_slack_oauth_state_is_signed_and_a_forged_one_cannot_take_over_an_organization(slack_env):
    org_id = uuid.UUID(slack_env.org_id)
    url = slack_service.get_oauth_url(org_id)
    state = httpx.URL(url).params["state"]
    assert state != str(org_id) and slack_service.verify_oauth_state(state) == org_id

    slack_env.fake.on("POST", "/api/oauth.v2.access", Resp(200, {"ok": True, "access_token": "xoxb-attacker", "team": {"id": "TATTACKER", "name": "Evil"}}))
    for forged in (str(org_id), state[:-3] + "abc", ""):
        response = await slack_env.client.get("/integrations/slack/callback", params={"code": "c", "state": forged})
        assert response.status_code == 400
    assert slack_env.fake.calls("POST", "/api/oauth.v2.access") == []  # nothing was even sent to Slack
    assert (await slack_env.db.scalar(select(SlackIntegration).where(SlackIntegration.organization_id == org_id))).team_id == "T1"  # untouched


async def test_slack_oauth_callback_with_a_valid_state_exchanges_the_code_and_stores_encrypted_tokens(slack_env):
    from api.security.secret_encryption import decrypt_secret

    org_id = uuid.UUID(slack_env.org_id)
    slack_env.fake.on("POST", "/api/oauth.v2.access", Resp(200, {"ok": True, "access_token": "xoxb-new", "team": {"id": "T9", "name": "Acme"}, "authed_user": {"access_token": "xoxp-user"}}))
    state = slack_service.sign_oauth_state(org_id)
    response = await slack_env.client.get("/integrations/slack/callback", params={"code": "the-code", "state": state})
    assert response.status_code == 200 and response.json() == {"connected": True, "team_name": "Acme"}
    assert slack_env.fake.calls("POST", "/api/oauth.v2.access")[0].form() == {
        "client_id": "slack-client", "client_secret": "slack-client-secret", "code": "the-code", "redirect_uri": "https://app.example.test/integrations/slack/callback"}
    integration = await slack_env.db.scalar(select(SlackIntegration).where(SlackIntegration.organization_id == org_id))
    await slack_env.db.refresh(integration)
    assert integration.team_id == "T9" and decrypt_secret(integration.bot_token) == "xoxb-new" and integration.bot_token != "xoxb-new"


async def test_slack_oauth_errors_are_typed(slack_env, monkeypatch):
    state = slack_service.sign_oauth_state(uuid.UUID(slack_env.org_id))
    slack_env.fake.on("POST", "/api/oauth.v2.access", Resp(200, {"ok": False, "error": "invalid_code"}))
    assert (await slack_env.client.get("/integrations/slack/callback", params={"code": "x", "state": state})).status_code == 400
    monkeypatch.setattr(slack_service, "_SLACK_OAUTH_ACCESS_URL", f"{closed_url()}/oauth")
    assert (await slack_env.client.get("/integrations/slack/callback", params={"code": "x", "state": state})).status_code == 502
    expired = jwt.encode({"org": slack_env.org_id, "purpose": "slack_oauth_state", "iat": 1, "exp": 2}, settings.JWT_SECRET_KEY, algorithm="HS256")
    assert (await slack_env.client.get("/integrations/slack/callback", params={"code": "x", "state": expired})).status_code == 400


# --------------------------------------------------------------------------------------------------------------------------------- Discord


@pytest.fixture
async def discord_env(client, db_session, register_payload, monkeypatch):
    private = Ed25519PrivateKey.generate()
    monkeypatch.setattr(settings, "DISCORD_PUBLIC_KEY", private.public_key().public_bytes_raw().hex())
    monkeypatch.setattr(settings, "DISCORD_GATEWAY_SHARED_SECRET", "gateway-secret")
    with FakeVendor() as discord:
        monkeypatch.setattr(discord_service, "_DISCORD_API_BASE", f"{discord.url}/api/v10")
        _token, org_id, user_id = await _make_org(client, db_session, register_payload)
        agent_id = await _make_agent(db_session, org_id)
        integration = await save_discord_integration(db_session, uuid.UUID(org_id), {"guild_id": "G1", "bot_token": "discord-bot-token"}, user_id)
        integration.agent_id = uuid.UUID(agent_id)
        await db_session.commit()
        engine = Engine(monkeypatch, discord_service)
        # the deferred slash command opens its own session: give it one on the test database
        factory = async_sessionmaker(bind=db_session.bind, expire_on_commit=False, autoflush=False)
        monkeypatch.setattr(discord_service, "_session_factory", lambda: factory)
        yield type("DiscordEnv", (), {"client": client, "db": db_session, "fake": discord, "private": private, "engine": engine, "integration": integration})


async def post_interaction(env, payload: dict, *, sign: bool = True, tamper: bool = False):
    body = json.dumps(payload).encode()
    stamp = str(int(time.time()))
    signature = env.private.sign(stamp.encode() + body).hex()
    headers = {"X-Signature-Ed25519": signature, "X-Signature-Timestamp": stamp, "Content-Type": "application/json"} if sign else {"Content-Type": "application/json"}
    return await env.client.post("/integrations/discord/interactions", content=body + (b" " if tamper else b""), headers=headers)


def ask(question="what is RAG?", interaction_token="itoken-abc.DEF_123"):
    return {"type": 2, "id": "i1", "application_id": "app-1", "token": interaction_token, "guild_id": "G1", "data": {"name": "ask", "options": [{"name": "question", "value": question}]}}


async def test_discord_ping_pong_and_signature_failures(discord_env):
    assert (await post_interaction(discord_env, {"type": 1})).json() == {"type": 1}
    assert (await post_interaction(discord_env, {"type": 1}, sign=False)).status_code == 401
    assert (await post_interaction(discord_env, {"type": 1}, tamper=True)).status_code == 401
    other = Ed25519PrivateKey.generate()
    body = b'{"type":1}'
    forged = await discord_env.client.post("/integrations/discord/interactions", content=body, headers={"X-Signature-Ed25519": other.sign(b"1" + body).hex(), "X-Signature-Timestamp": "1"})
    assert forged.status_code == 401


async def test_discord_slow_command_is_deferred_then_answered_through_the_interaction_webhook(discord_env):
    discord_env.fake.on("PATCH", "/api/v10/webhooks/app-1/itoken-abc.DEF_123/messages/@original", Resp(200, {"id": "m1"}))
    response = await post_interaction(discord_env, ask())
    assert response.status_code == 200 and response.json() == {"type": 5}  # "thinking..." within Discord's 3 s window
    await asyncio.gather(*discord_service._background_tasks)
    (edit,) = discord_env.fake.calls("PATCH")
    assert edit.json() == {"content": "Answer to: what is RAG?"} and "authorization" not in edit.headers  # the interaction token in the URL is the credential
    assert discord_env.engine.questions == ["what is RAG?"]


async def test_discord_followup_that_fails_does_not_crash_the_task(discord_env):
    discord_env.fake.on("PATCH", "/api/v10/webhooks/*", Resp(500, {"message": "Internal Server Error"}))
    await post_interaction(discord_env, ask())
    await asyncio.gather(*discord_service._background_tasks)  # raises if the task died
    assert len(discord_env.fake.calls("PATCH")) == 1


async def test_discord_followup_survives_a_rate_limit(discord_env):
    discord_env.fake.on("PATCH", "/api/v10/webhooks/*", [Resp(429, {"message": "You are being rate limited.", "retry_after": 1.5}), Resp(200, {"id": "m"})])
    await post_interaction(discord_env, ask())
    await asyncio.gather(*discord_service._background_tasks)
    assert len(discord_env.fake.calls("PATCH")) == 2


async def test_discord_engine_failure_still_replaces_the_thinking_message(discord_env, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(discord_service, "run_chat_engine", boom)
    discord_env.fake.on("PATCH", "/api/v10/webhooks/*", Resp(200, {}))
    await post_interaction(discord_env, ask())
    await asyncio.gather(*discord_service._background_tasks)
    assert "went wrong" in discord_env.fake.calls("PATCH")[0].json()["content"]


async def test_discord_malicious_interaction_token_never_reaches_the_url(discord_env):
    await post_interaction(discord_env, ask(interaction_token="../../channels/1/messages"))
    await asyncio.gather(*discord_service._background_tasks)
    assert discord_env.fake.calls("PATCH") == []  # path traversal in the token is refused before any request


async def test_discord_help_and_unknown_guild_are_immediate(discord_env):
    help_payload = {"type": 2, "id": "i2", "application_id": "app-1", "token": "t", "guild_id": "G1", "data": {"name": "help"}}
    assert "/ask" in (await post_interaction(discord_env, help_payload)).json()["data"]["content"]
    unknown = {**help_payload, "guild_id": "OTHER"}
    assert "no active" in (await post_interaction(discord_env, unknown)).json()["data"]["content"]


async def test_discord_gateway_redelivery_is_answered_once(discord_env):
    event = {"guild_id": "G1", "id": "m-100", "channel_id": "C1", "author_id": "U1", "author_name": "ada", "content": "hello"}
    headers = {"X-Gateway-Secret": "gateway-secret"}
    first = (await discord_env.client.post("/integrations/discord/message", json=event, headers=headers)).json()
    second = (await discord_env.client.post("/integrations/discord/message", json=event, headers=headers)).json()
    assert first["duplicate"] is False and second["duplicate"] is True and second["response"] == first["response"] == "Answer to: hello"
    assert discord_env.engine.questions == ["hello"]
    assert len((await discord_env.db.scalars(select(DiscordMessage))).all()) == 1


async def test_discord_send_endpoint_reports_a_discord_failure_as_502(discord_env, register_payload):
    from api.models.user import User

    login = await discord_env.client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = str(discord_env.integration.organization_id)
    discord_env.fake.on("POST", "/api/v10/channels/C1/messages", Resp(403, {"message": "Missing Access", "code": 50001}))
    response = await discord_env.client.post(f"/organizations/{org}/integrations/discord/send", json={"channel_id": "C1", "text": "hi"}, headers=headers)
    assert response.status_code == 502 and "Missing Access" in response.json()["detail"]
    discord_env.fake._routes.clear()
    discord_env.fake.on("POST", "/api/v10/channels/C1/messages", Resp(200, {"id": "sent"}))
    ok = await discord_env.client.post(f"/organizations/{org}/integrations/discord/send", json={"channel_id": "C1", "text": "hi", "message_id": "m9"}, headers=headers)
    assert ok.status_code == 200
    request = discord_env.fake.calls("POST", "/api/v10/channels/C1/messages")[-1]
    assert request.headers["authorization"] == "Bot discord-bot-token" and request.json() == {"content": "hi", "message_reference": {"message_id": "m9"}}


# ---------------------------------------------------------------------------------------------------------------------------------- Teams

BOT_APP_ID = "11111111-2222-3333-4444-555555555555"
KID = "contract-kid"


@pytest.fixture
async def teams_env(client, db_session, register_payload, monkeypatch, tmp_path):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key(), as_dict=True)
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})

    async def keys():
        return {KID: jwk}

    teams_bot_auth._cache.update({"keys": {}, "fetched_at": 0.0})
    monkeypatch.setattr(teams_bot_auth, "_fetch_jwks", keys)
    teams_service._bot_token_cache.clear()
    with FakeVendor() as microsoft, FakeVendor(tls_directory=str(tmp_path)) as connector:
        monkeypatch.setattr(teams_service, "_BOT_TOKEN_URL", f"{microsoft.url}/botframework.com/oauth2/v2.0/token")
        counter = {"n": 0}

        def token(req):
            counter["n"] += 1
            return Resp(200, {"access_token": f"bot-access-{counter['n']}", "expires_in": 3600, "token_type": "Bearer"})

        microsoft.on("POST", "/botframework.com/oauth2/v2.0/token", token)
        connector.on("POST", "/v3/conversations/*", Resp(200, {"id": "reply-activity"}))
        # the SSRF-safe client refuses loopback by design; the connector fake is on loopback, so the client is swapped for a plain one that
        # still verifies TLS against the fake's certificate. (SSRF refusal itself is covered by tests/test_ssrf*.py.)
        monkeypatch.setattr(teams_service, "ssrf_safe_client", lambda timeout=None: httpx.AsyncClient(verify=connector.ca_file, timeout=timeout))
        _token, org_id, user_id = await _make_org(client, db_session, register_payload)
        agent_id = await _make_agent(db_session, org_id)
        integration = await save_teams_integration(db_session, uuid.UUID(org_id), {"tenant_id": "tenant-1", "bot_id": BOT_APP_ID, "bot_token": "bot-app-password"}, user_id)
        integration.agent_id = uuid.UUID(agent_id)
        await db_session.commit()
        engine = Engine(monkeypatch, teams_service)
        yield type("TeamsEnv", (), {"client": client, "db": db_session, "microsoft": microsoft, "connector": connector, "private": private, "engine": engine, "counter": counter})


def teams_token(private, *, serviceurl=None, aud=BOT_APP_ID):
    claims = {"aud": aud, "iss": "https://api.botframework.com", "exp": int(time.time()) + 600, "iat": int(time.time())}
    if serviceurl:
        claims["serviceurl"] = serviceurl
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": KID})


def activity(env, text="<at>Bot</at> what is RAG?", activity_id="act-1"):
    return {"type": "message", "id": activity_id, "text": text, "serviceUrl": env.connector.url, "channelData": {"tenant": {"id": "tenant-1"}},
            "from": {"id": "29:user", "name": "Ada"}, "recipient": {"id": f"28:{BOT_APP_ID}", "name": "Bot"}, "conversation": {"id": "19:conv@thread.tacv2"}}


async def post_activity(env, payload, token=None, service_claim="same"):
    token = token or teams_token(env.private, serviceurl=payload["serviceUrl"] if service_claim == "same" else service_claim)
    return await env.client.post("/integrations/teams/webhook", json=payload, headers={"Authorization": f"Bearer {token}"})


async def test_teams_message_is_answered_through_the_bot_framework_connector(teams_env):
    response = await post_activity(teams_env, activity(teams_env))
    assert response.status_code == 200
    assert teams_env.engine.questions == ["what is RAG?"]  # "<at>Bot</at>" stripped
    assert teams_env.microsoft.calls("POST")[0].form() == {
        "grant_type": "client_credentials", "client_id": BOT_APP_ID, "client_secret": "bot-app-password", "scope": "https://api.botframework.com/.default"}
    (post,) = teams_env.connector.calls("POST")
    assert post.path == "/v3/conversations/19%3Aconv%40thread.tacv2/activities/act-1"
    assert post.headers["authorization"] == "Bearer bot-access-1"
    body = post.json()
    assert body["type"] == "message" and body["text"] == "Answer to: what is RAG?" and body["replyToId"] == "act-1"
    assert body["from"]["id"] == f"28:{BOT_APP_ID}" and body["conversation"]["id"] == "19:conv@thread.tacv2"
    assert (await teams_env.db.scalar(select(TeamsMessage))).status == "done"


async def test_teams_duplicate_activity_is_acknowledged_but_not_answered_twice(teams_env):
    await post_activity(teams_env, activity(teams_env))
    await post_activity(teams_env, activity(teams_env))
    assert len(teams_env.engine.questions) == 1 and len(teams_env.connector.calls("POST")) == 1


async def test_teams_bot_token_is_cached_across_replies(teams_env):
    await post_activity(teams_env, activity(teams_env, activity_id="a1"))
    await post_activity(teams_env, activity(teams_env, activity_id="a2"))
    assert teams_env.counter["n"] == 1 and len(teams_env.connector.calls("POST")) == 2


async def test_teams_expired_bot_token_is_refreshed_once_on_a_401(teams_env):
    teams_env.connector._routes.clear()
    teams_env.connector.on("POST", "/v3/conversations/*", [Resp(401, {"error": {"code": "BotNotAuthorized"}}), Resp(200, {"id": "ok"})])
    await post_activity(teams_env, activity(teams_env))
    assert teams_env.counter["n"] == 2
    assert [r.headers["authorization"] for r in teams_env.connector.calls("POST")] == ["Bearer bot-access-1", "Bearer bot-access-2"]
    assert (await teams_env.db.scalar(select(TeamsMessage))).status == "done"


async def test_teams_refused_credentials_or_connector_failure_are_recorded_not_raised(teams_env):
    teams_env.microsoft._routes.clear()
    teams_env.microsoft.on("POST", "/botframework.com/oauth2/v2.0/token", Resp(401, {"error": "invalid_client", "error_description": "AADSTS7000215: Invalid client secret"}))
    assert (await post_activity(teams_env, activity(teams_env, activity_id="b1"))).status_code == 200
    assert (await teams_env.db.scalar(select(TeamsMessage).where(TeamsMessage.teams_message_id == "b1"))).status == "delivery_failed"
    assert teams_env.connector.calls("POST") == []
    teams_service._bot_token_cache.clear()
    teams_env.microsoft._routes.clear()
    teams_env.microsoft.on("POST", "/botframework.com/oauth2/v2.0/token", Resp(200, {"access_token": "t", "expires_in": 3600}))
    teams_env.connector._routes.clear()
    teams_env.connector.on("POST", "/v3/conversations/*", Resp(502, {"error": "bad gateway"}))
    assert (await post_activity(teams_env, activity(teams_env, activity_id="b2"))).status_code == 200
    assert (await teams_env.db.scalar(select(TeamsMessage).where(TeamsMessage.teams_message_id == "b2"))).status == "delivery_failed"


async def test_teams_authentication_failures_process_nothing(teams_env):
    payload = activity(teams_env)
    no_token = await teams_env.client.post("/integrations/teams/webhook", json=payload)
    wrong_audience = await post_activity(teams_env, payload, token=teams_token(teams_env.private, aud="someone-else", serviceurl=payload["serviceUrl"]))
    stranger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = await post_activity(teams_env, payload, token=teams_token(stranger, serviceurl=payload["serviceUrl"]))
    assert [r.status_code for r in (no_token, wrong_audience, forged)] == [401, 401, 401]
    assert teams_env.engine.questions == [] and teams_env.connector.calls("POST") == []


async def test_teams_token_vouching_for_another_service_url_is_refused(teams_env):
    payload = activity(teams_env)
    payload["serviceUrl"] = "https://attacker.example.test/"  # the reply (with the bot's credentials) would go there
    response = await post_activity(teams_env, payload, token=teams_token(teams_env.private, serviceurl="https://smba.trafficmanager.net/emea/"))
    assert response.status_code == 401
    assert teams_env.engine.questions == []


async def test_teams_non_https_service_url_is_never_posted_to(teams_env):
    payload = activity(teams_env)
    payload["serviceUrl"] = teams_env.microsoft.url  # plain http
    assert (await post_activity(teams_env, payload)).status_code == 200
    assert (await teams_env.db.scalar(select(TeamsMessage))).status == "delivery_failed"
    assert teams_env.microsoft.calls("POST") == [] or all("oauth2" in r.path for r in teams_env.microsoft.calls("POST"))


async def test_teams_non_message_activities_are_acknowledged_and_ignored(teams_env):
    payload = {**activity(teams_env), "type": "conversationUpdate"}
    assert (await post_activity(teams_env, payload)).status_code == 200
    assert teams_env.engine.questions == []
