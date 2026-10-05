"""The Discord gateway endpoint and the Microsoft Teams webhook trigger a paid RAG answer, so neither may be callable by an
anonymous client; and a body that is not a JSON object is a 400, never an unhandled JSONDecodeError (500)."""

import time
import uuid
from unittest.mock import AsyncMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from api.config import settings
from api.models.chat_integrations import TeamsIntegration
from api.models.organization import Organization
from api.security import teams_bot_auth
from api.security.teams_bot_auth import BOT_FRAMEWORK_ISSUER, TeamsAuthError, verify_teams_bearer

BOT_APP_ID = "11111111-2222-3333-4444-555555555555"
KID = "test-key-1"


# ---- Discord gateway shared secret -------------------------------------------------------------------------------------

async def test_discord_message_without_the_gateway_secret_is_refused(client, monkeypatch):
    monkeypatch.setattr(settings, "DISCORD_GATEWAY_SHARED_SECRET", "s3cret-gateway-value")
    for headers in ({}, {"X-Gateway-Secret": "wrong"}):
        response = await client.post("/integrations/discord/message", json={"guild_id": "1"}, headers=headers)
        assert response.status_code == 401


async def test_discord_message_fails_closed_when_no_secret_is_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "DISCORD_GATEWAY_SHARED_SECRET", None)
    response = await client.post("/integrations/discord/message", json={"guild_id": "1"}, headers={"X-Gateway-Secret": "anything"})
    assert response.status_code == 401


async def test_discord_message_with_the_right_secret_but_a_bad_body_is_a_400(client, monkeypatch):
    monkeypatch.setattr(settings, "DISCORD_GATEWAY_SHARED_SECRET", "s3cret-gateway-value")
    headers = {"X-Gateway-Secret": "s3cret-gateway-value"}
    assert (await client.post("/integrations/discord/message", content=b"not json", headers=headers)).status_code == 400
    assert (await client.post("/integrations/discord/message", content=b"", headers=headers)).status_code == 400
    assert (await client.post("/integrations/discord/message", json=[1, 2], headers=headers)).status_code == 400


async def test_discord_message_with_the_right_secret_and_an_unknown_guild_is_a_404(client, monkeypatch):
    monkeypatch.setattr(settings, "DISCORD_GATEWAY_SHARED_SECRET", "s3cret-gateway-value")
    response = await client.post("/integrations/discord/message", json={"guild_id": "nope"}, headers={"X-Gateway-Secret": "s3cret-gateway-value"})
    assert response.status_code == 404


# ---- Teams bearer verification ------------------------------------------------------------------------------------------

@pytest.fixture
def signing():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key(), as_dict=True)
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    return private, jwk


@pytest.fixture(autouse=True)
def _reset_jwks_cache():
    teams_bot_auth._cache.update({"keys": {}, "fetched_at": 0.0})
    yield
    teams_bot_auth._cache.update({"keys": {}, "fetched_at": 0.0})


def _token(private, *, aud=BOT_APP_ID, iss=BOT_FRAMEWORK_ISSUER, exp_in=600, kid=KID, algorithm="RS256", key=None):
    claims = {"aud": aud, "iss": iss, "exp": int(time.time()) + exp_in, "iat": int(time.time())}
    return jwt.encode(claims, key if key is not None else private, algorithm=algorithm, headers={"kid": kid})


def _serve_keys(monkeypatch, jwk):
    fetch = AsyncMock(return_value={KID: jwk})
    monkeypatch.setattr(teams_bot_auth, "_fetch_jwks", fetch)
    return fetch


async def test_a_valid_microsoft_token_is_accepted(signing, monkeypatch):
    private, jwk = signing
    _serve_keys(monkeypatch, jwk)
    claims = await verify_teams_bearer(f"Bearer {_token(private)}", [BOT_APP_ID])
    assert claims["aud"] == BOT_APP_ID and claims["iss"] == BOT_FRAMEWORK_ISSUER


@pytest.mark.parametrize("make", [
    lambda p: _token(p, aud="someone-elses-bot"),
    lambda p: _token(p, iss="https://evil.example"),
    lambda p: _token(p, exp_in=-3600),
])
async def test_wrong_audience_issuer_or_expiry_is_refused(signing, monkeypatch, make):
    private, jwk = signing
    _serve_keys(monkeypatch, jwk)
    with pytest.raises(TeamsAuthError):
        await verify_teams_bearer(f"Bearer {make(private)}", [BOT_APP_ID])


async def test_a_token_signed_by_another_key_is_refused(signing, monkeypatch):
    _, jwk = signing
    _serve_keys(monkeypatch, jwk)
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(TeamsAuthError):
        await verify_teams_bearer(f"Bearer {_token(attacker)}", [BOT_APP_ID])


async def test_algorithm_confusion_with_the_public_key_as_hmac_secret_is_refused(signing, monkeypatch):
    private, jwk = signing
    _serve_keys(monkeypatch, jwk)
    forged = _token(private, algorithm="HS256", key="a-shared-secret-of-sufficient-length-for-hs256!")
    with pytest.raises(TeamsAuthError):
        await verify_teams_bearer(f"Bearer {forged}", [BOT_APP_ID])


async def test_an_unknown_key_id_is_refused_after_one_refresh(signing, monkeypatch):
    private, jwk = signing
    fetch = _serve_keys(monkeypatch, jwk)
    with pytest.raises(TeamsAuthError, match="unknown signing key"):
        await verify_teams_bearer(f"Bearer {_token(private, kid='rotated-away')}", [BOT_APP_ID])
    assert fetch.await_count == 1


async def test_missing_or_malformed_header_and_missing_audience_are_refused(signing, monkeypatch):
    private, jwk = signing
    _serve_keys(monkeypatch, jwk)
    for header in (None, "", "Bearer", "Basic abc", "Bearer not.a.jwt"):
        with pytest.raises(TeamsAuthError):
            await verify_teams_bearer(header, [BOT_APP_ID])
    with pytest.raises(TeamsAuthError, match="no Teams bot app id"):
        await verify_teams_bearer(f"Bearer {_token(private)}", [None, ""])


async def test_failing_to_load_the_signing_keys_refuses_the_request(signing, monkeypatch):
    private, _ = signing
    monkeypatch.setattr(teams_bot_auth, "_fetch_jwks", AsyncMock(side_effect=RuntimeError("network down")))
    with pytest.raises(TeamsAuthError, match="could not load"):
        await verify_teams_bearer(f"Bearer {_token(private)}", [BOT_APP_ID])


# ---- Teams webhook endpoint ---------------------------------------------------------------------------------------------

def _activity(tenant="tenant-1", kind="message"):
    return {"type": kind, "text": "hello", "from": {"id": "u1", "name": "U"}, "conversation": {"id": "c1"},
            "channelData": {"tenant": {"id": tenant}}, "serviceUrl": "https://smba.trafficmanager.net/emea/", "id": "a1"}


async def test_teams_webhook_without_a_token_is_401_and_processes_nothing(client, monkeypatch):
    monkeypatch.setattr(settings, "TEAMS_BOT_ID", BOT_APP_ID)
    processed = AsyncMock()
    monkeypatch.setattr("api.routers.chat_integrations_teams.process_teams_message", processed)
    response = await client.post("/integrations/teams/webhook", json=_activity())
    assert response.status_code == 401
    processed.assert_not_awaited()


async def test_teams_webhook_fails_closed_when_no_bot_id_is_configured(client, signing, monkeypatch):
    private, jwk = signing
    _serve_keys(monkeypatch, jwk)
    monkeypatch.setattr(settings, "TEAMS_BOT_ID", None)
    response = await client.post("/integrations/teams/webhook", json=_activity(), headers={"Authorization": f"Bearer {_token(private)}"})
    assert response.status_code == 401


async def test_teams_webhook_bad_body_is_a_400(client, monkeypatch):
    monkeypatch.setattr(settings, "TEAMS_BOT_ID", BOT_APP_ID)
    assert (await client.post("/integrations/teams/webhook", content=b"nope")).status_code == 400
    assert (await client.post("/integrations/teams/webhook", json=["x"])).status_code == 400


async def test_teams_webhook_with_a_valid_token_runs_the_integration_of_that_tenant_only(client, db_session, signing, monkeypatch):
    private, jwk = signing
    _serve_keys(monkeypatch, jwk)
    monkeypatch.setattr(settings, "TEAMS_BOT_ID", None)
    organization = Organization(name="Teams Org", slug=f"teams-{uuid.uuid4().hex[:8]}")
    db_session.add(organization)
    await db_session.flush()
    db_session.add(TeamsIntegration(organization_id=organization.id, tenant_id="tenant-1", bot_id=BOT_APP_ID, is_active=True))
    await db_session.commit()
    processed = AsyncMock()
    monkeypatch.setattr("api.routers.chat_integrations_teams.process_teams_message", processed)
    headers = {"Authorization": f"Bearer {_token(private)}"}

    ok = await client.post("/integrations/teams/webhook", json=_activity(tenant="tenant-1"), headers=headers)
    assert ok.status_code == 200 and processed.await_count == 1

    other_tenant = await client.post("/integrations/teams/webhook", json=_activity(tenant="tenant-2"), headers=headers)
    assert other_tenant.status_code == 401  # the token's audience is tenant-1's bot, not tenant-2's: nothing runs
    assert processed.await_count == 1


async def test_teams_webhook_ignores_non_message_activities_after_authentication(client, signing, monkeypatch):
    private, jwk = signing
    _serve_keys(monkeypatch, jwk)
    monkeypatch.setattr(settings, "TEAMS_BOT_ID", BOT_APP_ID)
    processed = AsyncMock()
    monkeypatch.setattr("api.routers.chat_integrations_teams.process_teams_message", processed)
    response = await client.post("/integrations/teams/webhook", json=_activity(kind="conversationUpdate"), headers={"Authorization": f"Bearer {_token(private)}"})
    assert response.status_code == 200 and response.json() == {"ok": True}
    processed.assert_not_awaited()
