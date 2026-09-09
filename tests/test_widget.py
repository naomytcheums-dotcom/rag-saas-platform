"""Partie 9.3.1 (script tag) through 9.3.10 (theme) -- the embeddable
widget."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse
from sqlalchemy import select

from api.config import settings
from api.models.agent import Agent
from api.models.widget import WidgetConfig, WidgetSuggestedQuestion
from api.security.widget_auth import create_widget_session_token, verify_widget_session_token
from api.services.widget import (
    generate_css_variables, generate_widget_short_name, get_default_avatar, get_mobile_position, get_position_css,
    sanitize_custom_css, sanitize_welcome_message, validate_theme, validate_theme_colors, validate_widget_name,
    validate_widget_params, validate_widget_position, validate_welcome_message, WidgetError,
)


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    return access_token


async def _make_org(client, db_session, register_payload):
    token = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": "Widget Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id


async def _make_agent(db_session, org_id: str) -> str:
    # idk_threshold=0.0 (not the default None -- see agent_idk.py's own
    # top docstring: None means "use the platform default", not
    # "disabled") -- this test's real purpose is the widget's own
    # session/chat transport, not Partie 6.2.3's own dedicated IDK
    # guardrail (test_agent_idk.py), which would otherwise override the
    # mocked LLM response with a real "I don't know" fallback since the
    # mocked search_with_context([]) below yields no real citations.
    agent = Agent(organization_id=uuid.UUID(org_id), name="Widget Agent", system_prompt="You are helpful.", idk_threshold=0.0)
    db_session.add(agent)
    await db_session.flush()
    await db_session.commit()
    return str(agent.id)


# ------------------------------------------------------------------- 9.3.1 Script tag


async def test_widget_script_serve(client):
    """Validation criterion: test_widget_script_serve."""
    response = await client.get("/widget/script.js")
    assert response.status_code == 200
    assert "application/javascript" in response.headers["content-type"]
    assert "RAGWidget" in response.text
    assert "max-age=3600" in response.headers["cache-control"]


async def test_widget_embed_js_alias_serves_the_same_script(client):
    response = await client.get("/widget/embed.js")
    assert response.status_code == 200
    assert "RAGWidget" in response.text


async def test_widget_config_params(client, db_session, register_payload):
    """Validation criterion: test_widget_config_params."""
    token, org_id = await _make_org(client, db_session, register_payload)
    await client.get(f"/organizations/{org_id}/widget/suggested-questions/admin", headers=_auth_header(token))  # forces lazy creation
    config = (await db_session.scalars(select(WidgetConfig).where(WidgetConfig.organization_id == uuid.UUID(org_id)))).first()
    assert config is not None

    response = await client.get(f"/widget/config?key={config.public_key}&theme=dark&position=top-left")
    assert response.status_code == 200
    data = response.json()
    assert data["theme"] == "dark"
    assert data["position"] == "top-left"


async def test_widget_config_unknown_key_returns_404(client):
    response = await client.get("/widget/config?key=wgt_does-not-exist")
    assert response.status_code == 404


def test_validate_widget_params_drops_invalid_values():
    """Validation criterion: les paramètres sont validés."""
    assert validate_widget_params({"theme": "not-a-theme", "position": "bottom-right"}) == {"position": "bottom-right"}


# ------------------------------------------------------------------- 9.3.1 Security -- session tokens, not the secret key


async def test_widget_security_public_key_cannot_send_messages(client):
    """Validation criterion: test_widget_security -- les clés API sont
    sécurisées: a real, syntactically plausible public key alone is
    NOT a valid /widget/chat bearer token (a real JWT session token
    is required instead -- see api/security/widget_auth.py)."""
    response = await client.post("/widget/chat", json={"message": "hi"}, headers={"Authorization": "Bearer wgt_some-real-looking-public-key"})
    assert response.status_code == 401


async def test_widget_session_token_round_trips():
    org_id, config_id, agent_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    token = create_widget_session_token(config_id, org_id, agent_id)
    session = verify_widget_session_token(token)
    assert session.organization_id == org_id
    assert session.widget_config_id == config_id
    assert session.agent_id == agent_id


async def test_widget_streaming(client, db_session, register_payload, monkeypatch):
    """Validation criterion: test_widget_streaming -- a real end-to-end
    session -> chat round trip (mocking the LLM call the same way
    tests/test_public_api.py already does for its own /v1/chat test,
    so this exercises the SAME real handle_public_chat engine, not a
    widget-only copy)."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Hello from the widget!")))
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[]))

    token, org_id = await _make_org(client, db_session, register_payload)
    agent_id = await _make_agent(db_session, org_id)
    await client.patch(f"/organizations/{org_id}/widget/agent", json={"agent_id": agent_id}, headers=_auth_header(token))

    config = (await db_session.scalars(select(WidgetConfig).where(WidgetConfig.organization_id == uuid.UUID(org_id)))).first()
    session_response = await client.post("/widget/session", json={"public_key": config.public_key})
    assert session_response.status_code == 200
    session_token = session_response.json()["session_token"]

    chat_response = await client.post("/widget/chat", json={"message": "Hi there"}, headers={"Authorization": f"Bearer {session_token}"})
    assert chat_response.status_code == 200
    assert chat_response.json()["response"] == "Hello from the widget!"


async def test_widget_chat_without_agent_configured_returns_400(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)
    await client.get(f"/organizations/{org_id}/widget/suggested-questions/admin", headers=_auth_header(token))
    config = (await db_session.scalars(select(WidgetConfig).where(WidgetConfig.organization_id == uuid.UUID(org_id)))).first()
    session_token = (await client.post("/widget/session", json={"public_key": config.public_key})).json()["session_token"]

    response = await client.post("/widget/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {session_token}"})
    assert response.status_code == 400


# ------------------------------------------------------------------- 9.3.1 iframe


async def test_widget_iframe_communication(client, db_session, register_payload):
    """Validation criterion: test_widget_iframe_communication -- the
    iframe is served with real headers allowing embedding (its own
    postMessage bridge is a real, client-side-only concern covered by
    frontend/widget/chat.js/embed.js, not something a backend test can
    exercise)."""
    token, org_id = await _make_org(client, db_session, register_payload)
    await client.get(f"/organizations/{org_id}/widget/suggested-questions/admin", headers=_auth_header(token))
    config = (await db_session.scalars(select(WidgetConfig).where(WidgetConfig.organization_id == uuid.UUID(org_id)))).first()

    response = await client.get(f"/widget/iframe?key={config.public_key}")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert response.headers["x-frame-options"] == "ALLOWALL"
    assert "frame-ancestors *" in response.headers["content-security-policy"]


async def test_widget_iframe_unknown_key_returns_404(client):
    response = await client.get("/widget/iframe?key=wgt_nope")
    assert response.status_code == 404


# ------------------------------------------------------------------- 9.3.1/9.4 CORS


async def test_widget_cors(client):
    """Validation criterion: test_widget_cors -- les CORS sont
    configurés (default WIDGET_CORS_ALLOWED_ORIGINS=["*"])."""
    response = await client.get("/widget/script.js", headers={"Origin": "https://third-party-site.example"})
    assert response.headers["access-control-allow-origin"] == "https://third-party-site.example"

    preflight = await client.options("/widget/config", headers={"Origin": "https://third-party-site.example", "Access-Control-Request-Method": "GET"})
    assert preflight.status_code == 204
    assert preflight.headers["access-control-allow-origin"] == "https://third-party-site.example"


async def test_widget_cors_does_not_apply_to_non_widget_routes(client):
    response = await client.get("/health", headers={"Origin": "https://third-party-site.example"})
    assert "access-control-allow-origin" not in response.headers or response.headers.get("access-control-allow-origin") != "https://third-party-site.example"


# ------------------------------------------------------------------- 9.3.3/9.3.10 Colors + theme


def test_validate_theme_colors_accepts_real_hex():
    validate_theme_colors({"primary_color": "#6C63FF"})


def test_validate_theme_colors_rejects_invalid_hex():
    with pytest.raises(WidgetError):
        validate_theme_colors({"primary_color": "not-a-color"})


def test_validate_theme_rejects_unknown_theme():
    with pytest.raises(WidgetError):
        validate_theme("solarized")


def test_generate_css_variables_includes_every_color():
    config = WidgetConfig(
        organization_id=uuid.uuid4(), primary_color="#6C63FF", secondary_color="#4A47A3", text_color="#FFFFFF",
        background_color="#FFFFFF", header_background="#6C63FF", border_radius="12px", font_family="system-ui",
    )
    css = generate_css_variables(config)
    assert "--widget-primary:#6C63FF" in css
    assert "--widget-radius:12px" in css


def test_sanitize_custom_css_rejects_javascript_url():
    with pytest.raises(WidgetError):
        sanitize_custom_css("body{background:url(javascript:alert(1))}")


def test_sanitize_custom_css_allows_real_css():
    assert sanitize_custom_css(".rw-app{color:red}") == ".rw-app{color:red}"


async def test_widget_theme_update_and_reset(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)

    update = await client.patch(f"/organizations/{org_id}/widget/theme", json={"theme": "dark"}, headers=_auth_header(token))
    assert update.status_code == 200
    assert update.json()["theme"] == "dark"

    reset = await client.post(f"/organizations/{org_id}/widget/theme/reset", headers=_auth_header(token))
    assert reset.status_code == 200
    assert reset.json()["theme"] == "auto"


async def test_widget_theme_rejects_invalid_theme(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)
    response = await client.patch(f"/organizations/{org_id}/widget/theme", json={"theme": "not-a-theme"}, headers=_auth_header(token))
    assert response.status_code == 400


# ------------------------------------------------------------------- 9.3.4 Name


def test_validate_widget_name_rejects_too_short():
    with pytest.raises(WidgetError):
        validate_widget_name("A")


def test_generate_widget_short_name():
    assert generate_widget_short_name("Support Bot") == "Support"


async def test_widget_name_update(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)
    response = await client.patch(f"/organizations/{org_id}/widget/config/name", json={"name": "My Assistant"}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["name"] == "My Assistant"
    assert response.json()["short_name"] == "My"


# ------------------------------------------------------------------- 9.3.6 Welcome message


def test_validate_welcome_message_rejects_too_long():
    with pytest.raises(WidgetError):
        validate_welcome_message("x" * 501)


def test_sanitize_welcome_message_strips_disallowed_tags():
    cleaned = sanitize_welcome_message("<script>alert(1)</script><p>Hi <strong>there</strong></p>")
    assert "<script>" not in cleaned
    assert "<strong>there</strong>" in cleaned


async def test_widget_welcome_update_and_reset(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)
    update = await client.patch(f"/organizations/{org_id}/widget/welcome", json={"message": "Welcome to our real support chat!"}, headers=_auth_header(token))
    assert update.status_code == 200
    assert "Welcome to our real support chat" in update.json()["message"]

    reset = await client.post(f"/organizations/{org_id}/widget/welcome/reset", headers=_auth_header(token))
    assert reset.status_code == 200
    assert reset.json()["message"] is None


# ------------------------------------------------------------------- 9.3.8 Position


def test_validate_widget_position_rejects_unknown():
    with pytest.raises(WidgetError):
        validate_widget_position("center")


def test_get_position_css():
    assert get_position_css("bottom-right", 20, 30) == "position:fixed;bottom:30px;right:20px;"


def test_get_mobile_position_collapses_top_to_bottom():
    assert get_mobile_position("top-left") == "bottom-left"


async def test_widget_position_update(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)
    response = await client.patch(f"/organizations/{org_id}/widget/position", json={"position": "top-left", "offset_x": 10}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["position"] == "top-left"
    assert response.json()["offset_x"] == 10


async def test_widget_position_rejects_invalid_offset(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)
    response = await client.patch(f"/organizations/{org_id}/widget/position", json={"offset_x": 9999}, headers=_auth_header(token))
    assert response.status_code == 400


# ------------------------------------------------------------------- 9.3.9 Language


async def test_widget_language_update_and_validation(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)
    ok = await client.patch(f"/organizations/{org_id}/widget/language", json={"language": "fr"}, headers=_auth_header(token))
    assert ok.status_code == 200
    assert ok.json()["language"] == "fr"

    invalid = await client.patch(f"/organizations/{org_id}/widget/language", json={"language": "klingon"}, headers=_auth_header(token))
    assert invalid.status_code == 400


async def test_widget_languages_endpoint_lists_supported(client):
    response = await client.get("/widget/languages")
    assert response.status_code == 200
    assert "en" in response.json()["languages"]
    assert "fr" in response.json()["languages"]


# ------------------------------------------------------------------- 9.3.2 Logo + 9.3.5 Avatar


async def test_widget_logo_upload_rejects_invalid_file(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)
    response = await client.post(
        f"/organizations/{org_id}/widget/logo",
        files={"file": ("not-an-image.txt", b"hello world", "text/plain")},
        headers=_auth_header(token),
    )
    assert response.status_code == 400


async def test_widget_avatar_default_fallback():
    """Validation criterion: test_widget_avatar_fallback."""
    fallback = get_default_avatar("Support Bot")
    assert fallback == {"type": "initial", "initial": "S"}


async def test_widget_avatar_upload_rejects_invalid_file(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)
    response = await client.post(
        f"/organizations/{org_id}/widget/avatar",
        files={"file": ("not-an-image.txt", b"hello world", "text/plain")},
        headers=_auth_header(token),
    )
    assert response.status_code == 400


async def test_widget_avatar_get_defaults_to_initial(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)
    await client.get(f"/organizations/{org_id}/widget/suggested-questions/admin", headers=_auth_header(token))
    config = (await db_session.scalars(select(WidgetConfig).where(WidgetConfig.organization_id == uuid.UUID(org_id)))).first()
    response = await client.get(f"/widget/avatar?key={config.public_key}")
    assert response.status_code == 200
    assert response.json()["type"] == "initial"


# ------------------------------------------------------------------- 9.3.7 Suggested questions


async def test_widget_suggested_questions_add_update_delete_reorder(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)

    q1 = (await client.post(f"/organizations/{org_id}/widget/suggested-questions", json={"question": "How does this work?"}, headers=_auth_header(token))).json()
    q2 = (await client.post(f"/organizations/{org_id}/widget/suggested-questions", json={"question": "What are your prices?"}, headers=_auth_header(token))).json()
    assert q1["position"] == 0
    assert q2["position"] == 1

    updated = await client.patch(f"/organizations/{org_id}/widget/suggested-questions/{q1['id']}", json={"question": "How does it work exactly?"}, headers=_auth_header(token))
    assert updated.status_code == 200
    assert updated.json()["question"] == "How does it work exactly?"

    reordered = await client.patch(
        f"/organizations/{org_id}/widget/suggested-questions/reorder",
        json={"question_ids": [q2["id"], q1["id"]]}, headers=_auth_header(token),
    )
    assert reordered.status_code == 200
    assert [q["id"] for q in reordered.json()] == [q2["id"], q1["id"]]

    deleted = await client.delete(f"/organizations/{org_id}/widget/suggested-questions/{q1['id']}", headers=_auth_header(token))
    assert deleted.status_code == 200

    listed = await client.get(f"/organizations/{org_id}/widget/suggested-questions/admin", headers=_auth_header(token))
    assert len(listed.json()) == 1


async def test_widget_suggested_questions_limit(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)
    for i in range(6):
        response = await client.post(f"/organizations/{org_id}/widget/suggested-questions", json={"question": f"Question {i}?"}, headers=_auth_header(token))
        assert response.status_code == 200

    over_limit = await client.post(f"/organizations/{org_id}/widget/suggested-questions", json={"question": "One too many?"}, headers=_auth_header(token))
    assert over_limit.status_code == 400


async def test_widget_suggested_questions_public_get_returns_only_active(client, db_session, register_payload):
    token, org_id = await _make_org(client, db_session, register_payload)
    q = (await client.post(f"/organizations/{org_id}/widget/suggested-questions", json={"question": "Visible?"}, headers=_auth_header(token))).json()
    await client.patch(f"/organizations/{org_id}/widget/suggested-questions/{q['id']}", json={"is_active": False}, headers=_auth_header(token))

    config = (await db_session.scalars(select(WidgetConfig).where(WidgetConfig.organization_id == uuid.UUID(org_id)))).first()
    public = await client.get(f"/widget/suggested-questions?key={config.public_key}")
    assert public.json() == []
