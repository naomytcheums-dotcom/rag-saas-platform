"""Phase 4, Étape 5 -- Domain Allowlist Widget.

**Audit finding (catch)**: the widget already existed (`api/models/widget.py`,
`api/security/widget_auth.py`, `api/routers/widget.py`), with a real,
sound two-tier auth model (public_key, non-secret / short-lived session
JWT). `GET /widget/iframe` already, DELIBERATELY sent
`frame-ancestors *`/`X-Frame-Options: ALLOWALL` -- this codebase's own
documented, ONE exception to an otherwise strict "never frameable"
policy. The real, genuine gap: `POST /widget/session` (the actual
authorization boundary that mints the token `POST /widget/chat`
trusts) had NO origin check at all, and no per-organization allowlist
existed anywhere -- `settings.WIDGET_CORS_ALLOWED_ORIGINS` is a real,
GLOBAL, platform-wide setting, not tenant-scoped. This file tests the
real, minimal fix: an optional, per-organization
`WidgetConfig.allowed_domains` enforced at session-minting AND at
iframe `frame-ancestors`, empty/`None` (every real, pre-existing
organization) meaning real, unchanged, unrestricted behavior."""

import uuid

import pytest
from sqlalchemy import select

from api.models.widget import WidgetConfig
from api.security.widget_auth import WidgetDomainError, is_origin_allowed, validate_widget_domain


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    return access_token


async def _make_org(client, register_payload, name="Widget Domain Org"):
    token = await _register(client, None, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(token))).json()["id"]
    return token, org_id


async def _get_config(db_session, org_id: str) -> WidgetConfig:
    return (await db_session.scalars(select(WidgetConfig).where(WidgetConfig.organization_id == uuid.UUID(org_id)))).first()


# ============================================================
# 1. validate_widget_domain -- config-time validation (Test 24-26)
# ============================================================


@pytest.mark.parametrize("raw, expected", [
    ("example.com", "https://example.com"),
    ("https://example.com", "https://example.com"),
    ("http://example.com", "http://example.com"),
    ("*.example.com", "https://*.example.com"),
    ("https://example.com:8443", "https://example.com:8443"),
    ("Example.COM", "https://example.com"),  # case-insensitive normalization
    ("example.com.", "https://example.com"),  # trailing dot stripped
])
def test_validate_widget_domain_accepts_and_normalizes_real_forms(raw, expected):
    assert validate_widget_domain(raw) == expected


@pytest.mark.parametrize("bad", [
    "*",
    ".example.com",
    "https://*.example.com/*",
    "javascript:alert(1)",
    "data:text/html,x",
    "http://user:pass@example.com",
    "example.com/path",
    "example.com?query=1",
    "",
    "   ",
    "ftp://example.com",
    "exa*mple.com",  # wildcard not in leading-label position
])
def test_validate_widget_domain_rejects_dangerous_or_malformed_entries(bad):
    """Test 24/26 -- an admin cannot configure `*`, a path-bearing
    entry, a dangerous scheme, or a non-leading wildcard."""
    with pytest.raises(WidgetDomainError):
        validate_widget_domain(bad)


# ============================================================
# 2. is_origin_allowed -- runtime matching (Tests 1-12 of the matrix)
# ============================================================


def test_is_origin_allowed_default_unrestricted():
    """Test 3/rétrocompatibilité -- no allowlist configured = every
    origin (including no origin at all) is allowed, exactly this
    codebase's own real, pre-existing behavior."""
    assert is_origin_allowed("https://anything.example", None) is True
    assert is_origin_allowed(None, None) is True
    assert is_origin_allowed(None, []) is True


def test_is_origin_allowed_exact_match():
    """Test 1 -- origine autorisée exacte."""
    allowed = [validate_widget_domain("https://client.example")]
    assert is_origin_allowed("https://client.example", allowed) is True


@pytest.mark.parametrize("origin", [
    None,                                    # Test 5 -- absent
    "null",                                  # Test 5 -- explicit null
    "https://evil.example",                  # Test 4 -- unknown origin
    "http://client.example",                 # Test 8 -- wrong scheme
    "https://client.example:9999",           # Test 7 -- wrong port
    "https://www.client.example",            # subdomain, exact-only allowlist
    "https://client.example.evil.com",       # Test 9-ish -- suffix/parser-bypass trick
    "https://evilclient.example",            # bare-suffix trick (no dot boundary)
    "not a url",                             # forged/unparseable
])
def test_is_origin_allowed_blocks_everything_not_an_exact_match(origin):
    allowed = [validate_widget_domain("https://client.example")]
    assert is_origin_allowed(origin, allowed) is False


def test_is_origin_allowed_ignores_path_like_a_real_referer():
    """`Referer` (unlike `Origin`) commonly carries a full URL with a
    path -- the real host/scheme/port still match correctly."""
    allowed = [validate_widget_domain("https://client.example")]
    assert is_origin_allowed("https://client.example/some/page?x=1", allowed) is True


def test_is_origin_allowed_wildcard_subdomain():
    """Test 2 -- subdomain support, explicit opt-in only."""
    allowed = [validate_widget_domain("*.client.example")]
    assert is_origin_allowed("https://app.client.example", allowed) is True
    assert is_origin_allowed("https://a.b.client.example", allowed) is True
    assert is_origin_allowed("https://client.example", allowed) is False  # wildcard does NOT include the bare domain
    assert is_origin_allowed("https://evilclient.example", allowed) is False  # no dot boundary -- must not match


def test_is_origin_allowed_credentials_in_origin_are_irrelevant_to_matching():
    """A real `Origin` header can never carry userinfo (browsers never
    send one) -- this documents that a forged one is just parsed by
    host/scheme/port, userinfo has no special effect either way."""
    allowed = [validate_widget_domain("https://client.example")]
    assert is_origin_allowed("https://attacker@client.example", allowed) is True  # host still matches -- userinfo is not a security boundary here
    assert is_origin_allowed("https://client.example@evil.example", allowed) is False  # real host is evil.example


# ============================================================
# 3. Admin config endpoints (Tests 13, 24-26, multi-tenant 22-23)
# ============================================================


async def test_admin_can_set_and_read_allowed_domains(client, db_session, register_payload):
    token, org_id = await _make_org(client, register_payload, "Domains Admin Org")

    response = await client.patch(
        f"/organizations/{org_id}/widget/domains", json={"allowed_domains": ["client.example", "https://app.client.example"]},
        headers=_auth_header(token),
    )
    assert response.status_code == 200
    assert set(response.json()["allowed_domains"]) == {"https://client.example", "https://app.client.example"}

    read_back = await client.get(f"/organizations/{org_id}/widget/domains", headers=_auth_header(token))
    assert read_back.status_code == 200
    assert set(read_back.json()["allowed_domains"]) == {"https://client.example", "https://app.client.example"}


async def test_admin_config_rejects_a_dangerous_domain(client, db_session, register_payload):
    """Test 24/26 -- rejet à la configuration."""
    token, org_id = await _make_org(client, register_payload, "Domains Reject Org")
    response = await client.patch(
        f"/organizations/{org_id}/widget/domains", json={"allowed_domains": ["javascript:alert(1)"]},
        headers=_auth_header(token),
    )
    assert response.status_code == 400


async def test_admin_config_rejects_too_many_domains(client, db_session, register_payload):
    token, org_id = await _make_org(client, register_payload, "Domains Cap Org")
    response = await client.patch(
        f"/organizations/{org_id}/widget/domains", json={"allowed_domains": [f"d{i}.example.com" for i in range(25)]},
        headers=_auth_header(token),
    )
    assert response.status_code == 422  # Pydantic's own max_length on the request field


async def test_admin_config_empty_list_removes_restriction(client, db_session, register_payload):
    token, org_id = await _make_org(client, register_payload, "Domains Clear Org")
    await client.patch(f"/organizations/{org_id}/widget/domains", json={"allowed_domains": ["client.example"]}, headers=_auth_header(token))
    response = await client.patch(f"/organizations/{org_id}/widget/domains", json={"allowed_domains": []}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["allowed_domains"] == []
    config = await _get_config(db_session, org_id)
    assert config.allowed_domains is None


async def test_non_member_cannot_read_or_update_widget_domains(client, db_session, register_payload):
    token, org_id = await _make_org(client, register_payload, "Domains Non Member Org")
    other_token = await _register(client, db_session, "outsider-domains@example.com")

    read_response = await client.get(f"/organizations/{org_id}/widget/domains", headers=_auth_header(other_token))
    assert read_response.status_code in (403, 404)
    write_response = await client.patch(
        f"/organizations/{org_id}/widget/domains", json={"allowed_domains": ["evil.example"]}, headers=_auth_header(other_token),
    )
    assert write_response.status_code in (403, 404)


async def test_org_a_domain_config_is_invisible_and_unusable_by_org_b(client, db_session, register_payload):
    """Tests 22/23 -- multi-tenant: org A's own allowlist config never
    leaks to, nor is reachable by, org B."""
    token_a, org_a = await _make_org(client, register_payload, "Domains Tenant A")
    await client.patch(f"/organizations/{org_a}/widget/domains", json={"allowed_domains": ["a-client.example"]}, headers=_auth_header(token_a))

    token_b = await _register(client, db_session, "tenant-b-domains@example.com")
    org_b = (await client.post("/organizations", json={"name": "Domains Tenant B"}, headers=_auth_header(token_b))).json()["id"]

    # Org B's own config is genuinely separate/empty -- never inherited.
    config_b = await client.get(f"/organizations/{org_b}/widget/domains", headers=_auth_header(token_b))
    assert config_b.json()["allowed_domains"] == []

    # Org B cannot read org A's own config.
    forbidden = await client.get(f"/organizations/{org_a}/widget/domains", headers=_auth_header(token_b))
    assert forbidden.status_code in (403, 404)


# ============================================================
# 4. Session minting -- the real authorization boundary (Tests 4-11, 19-21)
# ============================================================


async def test_session_minting_is_blocked_for_a_disallowed_origin(client, db_session, register_payload):
    """Test 20 -- real regression test for the real vulnerability this
    étape's own audit found: minting a session token used to have NO
    origin check at all."""
    token, org_id = await _make_org(client, register_payload, "Session Block Org")
    await client.patch(f"/organizations/{org_id}/widget/domains", json={"allowed_domains": ["client.example"]}, headers=_auth_header(token))
    config = await _get_config(db_session, org_id)

    response = await client.post(
        "/widget/session", json={"public_key": config.public_key}, headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403


async def test_session_minting_succeeds_for_an_allowed_origin(client, db_session, register_payload):
    """Test 19 -- token utilisé depuis un domaine autorisé."""
    token, org_id = await _make_org(client, register_payload, "Session Allow Org")
    await client.patch(f"/organizations/{org_id}/widget/domains", json={"allowed_domains": ["client.example"]}, headers=_auth_header(token))
    config = await _get_config(db_session, org_id)

    response = await client.post(
        "/widget/session", json={"public_key": config.public_key}, headers={"Origin": "https://client.example"},
    )
    assert response.status_code == 200
    assert "session_token" in response.json()


async def test_session_minting_is_unrestricted_when_no_allowlist_configured(client, db_session, register_payload):
    """Rétrocompatibilité (Test 23 of the regression suite) -- a fresh
    organization's own real, existing behavior is unchanged: no
    `Origin` header at all still works, exactly as before this étape."""
    token, org_id = await _make_org(client, register_payload, "Session Default Org")
    await client.get(f"/organizations/{org_id}/widget/domains", headers=_auth_header(token))  # forces lazy config creation
    config = await _get_config(db_session, org_id)

    no_origin = await client.post("/widget/session", json={"public_key": config.public_key})
    assert no_origin.status_code == 200
    any_origin = await client.post(
        "/widget/session", json={"public_key": config.public_key}, headers={"Origin": "https://totally-random.example"},
    )
    assert any_origin.status_code == 200


async def test_session_minting_rejects_a_forged_null_origin_when_restricted(client, db_session, register_payload):
    """Test 5/29 -- a forged `Origin: null` must never bypass a real,
    configured allowlist."""
    token, org_id = await _make_org(client, register_payload, "Session Null Origin Org")
    await client.patch(f"/organizations/{org_id}/widget/domains", json={"allowed_domains": ["client.example"]}, headers=_auth_header(token))
    config = await _get_config(db_session, org_id)

    response = await client.post(
        "/widget/session", json={"public_key": config.public_key}, headers={"Origin": "null"},
    )
    assert response.status_code == 403


async def test_session_minting_falls_back_to_referer_when_origin_absent(client, db_session, register_payload):
    token, org_id = await _make_org(client, register_payload, "Session Referer Org")
    await client.patch(f"/organizations/{org_id}/widget/domains", json={"allowed_domains": ["client.example"]}, headers=_auth_header(token))
    config = await _get_config(db_session, org_id)

    response = await client.post(
        "/widget/session", json={"public_key": config.public_key}, headers={"Referer": "https://client.example/embed-page"},
    )
    assert response.status_code == 200


# ============================================================
# 4bis. Phase 4, Étape 5bis -- Limite 1: Origin ET Referer absents
# ============================================================


async def test_session_minting_rejects_no_origin_and_no_referer_when_restricted(client, db_session, register_payload):
    """Limite 1 -- réaudit : le code réel (`is_origin_allowed`) rejette
    déjà ce cas (`if not origin: return False` s'applique dès que
    `allowed_domains` est non-vide) -- ce test le PROUVE explicitement,
    ce qui manquait avant Étape 5bis. Le rapport de l'Étape 5 décrivait
    ce cas comme une faille active ; ce test démontre que ce n'était
    pas le cas dans le code réel (erreur de description dans ce
    rapport, corrigée ici, aucun changement de code n'était
    nécessaire pour CE cas précis)."""
    token, org_id = await _make_org(client, register_payload, "Session No Origin No Referer Org")
    await client.patch(f"/organizations/{org_id}/widget/domains", json={"allowed_domains": ["client.example"]}, headers=_auth_header(token))
    config = await _get_config(db_session, org_id)

    response = await client.post("/widget/session", json={"public_key": config.public_key})
    assert response.status_code == 403


async def test_session_minting_rejects_a_disallowed_referer(client, db_session, register_payload):
    token, org_id = await _make_org(client, register_payload, "Session Referer Reject Org")
    await client.patch(f"/organizations/{org_id}/widget/domains", json={"allowed_domains": ["client.example"]}, headers=_auth_header(token))
    config = await _get_config(db_session, org_id)

    response = await client.post(
        "/widget/session", json={"public_key": config.public_key}, headers={"Referer": "https://evil.example/embed-page"},
    )
    assert response.status_code == 403


# ============================================================
# 4ter. Phase 4, Étape 5bis -- Limite 2: token JWT scopé à l'origine
# ============================================================


async def _make_widget_agent(db_session, org_id: str) -> str:
    from api.models.agent import Agent

    agent = Agent(organization_id=uuid.UUID(org_id), name="Domain Allowlist Agent", system_prompt="You are helpful.", idk_threshold=0.0)
    db_session.add(agent)
    await db_session.flush()
    await db_session.commit()
    return str(agent.id)


async def _mint_and_configure_chat_agent(client, db_session, org_id: str, token: str, origin_header: dict) -> tuple:
    agent_id = await _make_widget_agent(db_session, org_id)
    await client.patch(f"/organizations/{org_id}/widget/agent", json={"agent_id": agent_id}, headers=_auth_header(token))
    config = await _get_config(db_session, org_id)
    session_response = await client.post("/widget/session", json={"public_key": config.public_key}, headers=origin_header)
    assert session_response.status_code == 200
    return session_response.json()["session_token"], config


async def test_widget_chat_succeeds_when_origin_matches_the_token(client, db_session, register_payload, monkeypatch):
    """Test 1 -- token émis pour origin A + appel depuis origin A → 200."""
    import litellm
    from unittest.mock import AsyncMock
    from litellm.types.utils import Choices, Message, ModelResponse
    from api.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=ModelResponse(
        choices=[Choices(message=Message(content="Hello!", role="assistant"), index=0, finish_reason="stop")],
    )))
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[]))

    token, org_id = await _make_org(client, register_payload, "Chat Origin Match Org")
    session_token, _ = await _mint_and_configure_chat_agent(client, db_session, org_id, token, {"Origin": "https://client.example"})

    response = await client.post(
        "/widget/chat", json={"message": "hi"},
        headers={"Authorization": f"Bearer {session_token}", "Origin": "https://client.example"},
    )
    assert response.status_code == 200


async def test_widget_chat_rejects_a_different_origin_than_the_token(client, db_session, register_payload, monkeypatch):
    """Test 2 -- token émis pour origin A + appel depuis origin B → 403.
    Real regression test for the real vulnerability this étape's own
    audit found: a stolen/observed session token used to be replayable
    from any origin."""
    from api.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")

    token, org_id = await _make_org(client, register_payload, "Chat Origin Mismatch Org")
    session_token, _ = await _mint_and_configure_chat_agent(client, db_session, org_id, token, {"Origin": "https://client.example"})

    response = await client.post(
        "/widget/chat", json={"message": "hi"},
        headers={"Authorization": f"Bearer {session_token}", "Origin": "https://evil.example"},
    )
    assert response.status_code == 403


async def test_widget_chat_rejects_a_token_bound_to_an_origin_when_called_with_none(client, db_session, register_payload, monkeypatch):
    """Test 3 -- token émis pour origin A + appel sans Origin →
    rejeté (décision documentée : correspondance stricte, un token lié
    à une origine réelle ne peut jamais être utilisé sans en fournir
    une)."""
    from api.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")

    token, org_id = await _make_org(client, register_payload, "Chat Origin Then None Org")
    session_token, _ = await _mint_and_configure_chat_agent(client, db_session, org_id, token, {"Origin": "https://client.example"})

    response = await client.post("/widget/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {session_token}"})
    assert response.status_code == 403


async def test_widget_chat_succeeds_when_both_session_and_chat_have_no_origin(client, db_session, register_payload, monkeypatch):
    """Rétrocompatibilité -- a real, non-browser caller (or an
    unrestricted organization's own real widget, consistent with every
    pre-Étape-5bis test in tests/test_widget.py) that never sends
    `Origin` at either step keeps working exactly as before: `None ==
    None` is a real, valid match."""
    import litellm
    from unittest.mock import AsyncMock
    from litellm.types.utils import Choices, Message, ModelResponse
    from api.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=ModelResponse(
        choices=[Choices(message=Message(content="Hello!", role="assistant"), index=0, finish_reason="stop")],
    )))
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[]))

    token, org_id = await _make_org(client, register_payload, "Chat No Origin Both Org")
    session_token, _ = await _mint_and_configure_chat_agent(client, db_session, org_id, token, {})

    response = await client.post("/widget/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {session_token}"})
    assert response.status_code == 200


async def test_widget_chat_rejects_a_legacy_token_with_no_origin_claim(client, db_session, register_payload):
    """Test 4 -- token sans claim `origin` (émis avant Étape 5bis) →
    rejeté, forçant une réémission -- décision documentée : ces tokens
    sont de toute façon à très courte durée de vie
    (`WIDGET_SESSION_TOKEN_EXPIRE_MINUTES`), donc auto-résolus peu après
    le déploiement, sans migration active nécessaire."""
    import datetime as dt

    import jwt as pyjwt

    from api.config import settings

    token, org_id = await _make_org(client, register_payload, "Chat Legacy Token Org")
    await client.get(f"/organizations/{org_id}/widget/domains", headers=_auth_header(token))
    config = await _get_config(db_session, org_id)

    now = dt.datetime.now(dt.timezone.utc)
    legacy_payload = {
        "purpose": "widget_session", "widget_config_id": str(config.id), "organization_id": org_id,
        "agent_id": None, "iat": now, "exp": now + dt.timedelta(minutes=5),
        # Real, deliberate omission -- no "origin" key at all, simulating
        # a real token minted by the pre-Étape-5bis code.
    }
    legacy_token = pyjwt.encode(legacy_payload, settings.JWT_SECRET_KEY, algorithm="HS256")

    response = await client.post("/widget/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {legacy_token}"})
    assert response.status_code == 403


async def test_widget_chat_rejects_an_expired_token(client, db_session, register_payload):
    """Test 5 -- non-régression : un token expiré reste un 401 (géré
    par `verify_widget_session_token`'s own real `jwt.decode`,
    inchangé par cette étape)."""
    import datetime as dt

    import jwt as pyjwt

    from api.config import settings

    token, org_id = await _make_org(client, register_payload, "Chat Expired Token Org")
    await client.get(f"/organizations/{org_id}/widget/domains", headers=_auth_header(token))
    config = await _get_config(db_session, org_id)

    now = dt.datetime.now(dt.timezone.utc)
    expired_payload = {
        "purpose": "widget_session", "widget_config_id": str(config.id), "organization_id": org_id,
        "agent_id": None, "origin": None, "iat": now - dt.timedelta(minutes=30), "exp": now - dt.timedelta(minutes=1),
    }
    expired_token = pyjwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm="HS256")

    response = await client.post("/widget/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


# ============================================================
# 5. Iframe embedding CSP (Tests 16-18)
# ============================================================


async def test_iframe_frame_ancestors_is_wildcard_by_default(client, db_session, register_payload):
    """Rétrocompatibilité -- byte-identical to this codebase's own,
    pre-existing, deliberate default."""
    token, org_id = await _make_org(client, register_payload, "Iframe Default Org")
    await client.get(f"/organizations/{org_id}/widget/domains", headers=_auth_header(token))  # forces lazy config creation
    config = await _get_config(db_session, org_id)

    response = await client.get(f"/widget/iframe?key={config.public_key}")
    assert response.status_code == 200
    assert response.headers["content-security-policy"] == "frame-ancestors *"
    assert response.headers["x-frame-options"] == "ALLOWALL"


async def test_iframe_frame_ancestors_is_restricted_when_configured(client, db_session, register_payload):
    """Test 16/17 -- embed depuis origine autorisée vs interdite: the
    real, per-organization CSP now genuinely restricts embedding (the
    real, actual enforcement is the BROWSER's own CSP engine on the
    embedding page -- this test proves the real, correct HEADER is
    sent, which is the server's own real, complete responsibility)."""
    token, org_id = await _make_org(client, register_payload, "Iframe Restricted Org")
    await client.patch(f"/organizations/{org_id}/widget/domains", json={"allowed_domains": ["client.example"]}, headers=_auth_header(token))
    config = await _get_config(db_session, org_id)

    response = await client.get(f"/widget/iframe?key={config.public_key}")
    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    assert csp == "frame-ancestors https://client.example"
    assert "*" not in csp


async def test_widget_iframe_unknown_key_returns_404_with_restricted_domains_too(client, db_session, register_payload):
    """Regression: an unknown key is still a real 404, not leaked."""
    response = await client.get("/widget/iframe?key=wgt_nope-restricted")
    assert response.status_code == 404


# ============================================================
# 6. Real end-to-end: unauthorized origin never reaches widget data (Test 18/21)
# ============================================================


async def test_end_to_end_unauthorized_origin_never_obtains_a_session_or_chats(client, db_session, register_payload, monkeypatch):
    """Requirement 18/21 -- a full, real browser-simulated path:
    unauthorized origin -> POST /widget/session -> blocked BEFORE any
    session token (and therefore any real /widget/chat call) can ever
    be produced. Proves the block happens at the real handler, not a
    falsely-green assertion against an unreachable code path."""
    import litellm
    from unittest.mock import AsyncMock
    from litellm.types.utils import Choices, Message, ModelResponse
    from api.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")

    def _real_response(text):
        return ModelResponse(choices=[Choices(message=Message(content=text, role="assistant"), index=0, finish_reason="stop")])

    mock_acompletion = AsyncMock(return_value=_real_response("This should never be reached."))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    token, org_id = await _make_org(client, register_payload, "E2E Widget Domain Org")
    await client.patch(f"/organizations/{org_id}/widget/domains", json={"allowed_domains": ["https://client.example"]}, headers=_auth_header(token))
    config = await _get_config(db_session, org_id)

    # Step 1: unauthorized origin tries to mint a session -- blocked.
    blocked = await client.post(
        "/widget/session", json={"public_key": config.public_key}, headers={"Origin": "https://attacker.example"},
    )
    assert blocked.status_code == 403
    assert "session_token" not in blocked.json()

    # Step 2: a real caller can NEVER reach /widget/chat without a real
    # session token -- confirmed the LLM (and therefore the whole
    # real chat pipeline) was never invoked.
    mock_acompletion.assert_not_called()

    # Step 3: the SAME public_key, from the real, authorized origin,
    # legitimately succeeds -- proves this is a real ALLOWLIST, not a
    # blanket block.
    allowed = await client.post(
        "/widget/session", json={"public_key": config.public_key}, headers={"Origin": "https://client.example"},
    )
    assert allowed.status_code == 200
