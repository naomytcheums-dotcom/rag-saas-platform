"""Partie 5.4.6 -- HTTP workflow block. The real SSRF-safe transport
is mocked at the same clean boundary as tests/test_url_fetching.py
(`api.services.url_fetching._client`) -- this suite exercises the
block's own real logic (validation, rendering, SSRF pre-check,
response formatting), not httpx/DNS internals already covered there."""

import httpx
import pytest

from api.services.workflow_block_http import (
    execute_http_block, format_http_response, render_http_body, render_http_url, validate_http_config,
)
from api.services.workflow_blocks import WorkflowBlockError


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr("api.services.url_fetching._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


# --------------------------------------- validate_http_config / render_http_url / render_http_body --


def test_validate_http_config_accepts_a_real_valid_config():
    validate_http_config({"url": "https://example.com", "method": "POST"})


def test_validate_http_config_rejects_a_missing_url():
    """Validation criterion: la validation fonctionne."""
    with pytest.raises(WorkflowBlockError, match="url"):
        validate_http_config({})


def test_validate_http_config_rejects_an_unknown_method():
    with pytest.raises(WorkflowBlockError, match="Unknown HTTP method"):
        validate_http_config({"url": "https://example.com", "method": "TRACE"})


def test_validate_http_config_rejects_non_positive_timeout():
    with pytest.raises(WorkflowBlockError):
        validate_http_config({"url": "https://example.com", "timeout": 0})


def test_render_http_url_substitutes_real_variables():
    """Validation criterion: le rendu des URLs fonctionne."""
    assert render_http_url("https://example.com/{{path}}", {"path": "users"}) == "https://example.com/users"


def test_render_http_url_rejects_a_disallowed_scheme():
    """Validation criterion: sécurité -- schéma non http(s) rejeté avant tout réseau."""
    with pytest.raises(ValueError):
        render_http_url("file:///etc/passwd", {})


def test_render_http_body_renders_a_real_string_template():
    """Validation criterion: le rendu des corps fonctionne."""
    assert render_http_body("Hello {{name}}", {"name": "Ada"}) == "Hello Ada"


def test_render_http_body_renders_every_real_leaf_of_a_json_object():
    body = render_http_body({"greeting": "Hi {{name}}", "count": 3, "tags": ["{{tag}}"]}, {"name": "Ada", "tag": "vip"})
    assert body == {"greeting": "Hi Ada", "count": 3, "tags": ["vip"]}


def test_format_http_response_parses_real_json():
    response = httpx.Response(200, json={"ok": True}, request=httpx.Request("GET", "https://example.com"))
    formatted = format_http_response(response)
    assert formatted == {"status_code": 200, "headers": dict(response.headers), "body": {"ok": True}}


def test_format_http_response_falls_back_to_real_plain_text():
    response = httpx.Response(200, text="not json", request=httpx.Request("GET", "https://example.com"))
    assert format_http_response(response)["body"] == "not json"


# --------------------------------------- execute_http_block --


async def test_execute_http_block_returns_a_real_formatted_response(monkeypatch):
    """Validation criterion: l'exécution du bloc HTTP fonctionne."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": "ok"})

    _patch_client(monkeypatch, handler)
    result = await execute_http_block({"url": "https://example.com/api", "output_key": "resp"}, {})
    assert result["resp"]["body"] == {"result": "ok"}


async def test_execute_http_block_renders_real_url_and_body(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.com/users/42"
        assert request.content == b'{"id":"42"}'
        return httpx.Response(200, json={})

    _patch_client(monkeypatch, handler)
    await execute_http_block(
        {"url": "https://example.com/users/{{id}}", "method": "POST", "body": {"id": "{{id}}"}}, {"id": 42},
    )


async def test_execute_http_block_sends_real_headers(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "secret"
        return httpx.Response(200, json={})

    _patch_client(monkeypatch, handler)
    await execute_http_block({"url": "https://example.com", "headers": {"X-Api-Key": "secret"}}, {})


async def test_execute_http_block_raises_workflow_block_error_on_a_real_timeout(monkeypatch):
    """Validation criterion: robustesse -- que se passe-t-il si l'appel échoue."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    _patch_client(monkeypatch, handler)
    with pytest.raises(WorkflowBlockError, match="timed out"):
        await execute_http_block({"url": "https://example.com"}, {})


async def test_execute_http_block_rejects_a_disallowed_scheme_before_any_network_call(monkeypatch):
    """Validation criterion: sécurité -- SSRF (schéma non http(s))."""
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200)

    _patch_client(monkeypatch, handler)
    with pytest.raises(WorkflowBlockError):
        await execute_http_block({"url": "ftp://example.com/file"}, {})
    assert called is False


async def test_execute_http_block_raises_on_invalid_config():
    with pytest.raises(WorkflowBlockError):
        await execute_http_block({}, {})
