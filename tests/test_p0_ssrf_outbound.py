"""SEC-005: webhooks and MCP servers must not be a way into private networks (SSRF).

Before the fix a tenant owner could register `http://169.254.169.254/...` (or any internal service) as a webhook or MCP server URL;
the worker then POSTed to it with plain `httpx`, and the raw exception text was stored where the tenant can read it. These tests use a
real loopback listener to prove that no request reaches a private address, and mocked DNS/sockets for the rebinding and allowlist cases."""

import http.server
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpcore
import httpx
import pytest

from api.config import settings
from api.models.mcp_server import MCPServerConfig
from api.services.mcp.client import MCPClientError, discover_tools
from api.services.outbound_http import (
    OutboundURLError, describe_outbound_error, mcp_http_client, safe_webhook_client, validate_outbound_url,
)
from test_document_idor import make_tenants

PUBLIC_URLS = [
    "https://example.com", "https://example.com/hook", "http://example.com:8080/a?b=c", "https://hooks.example.org/x/y",
    "https://8.8.8.8/hook", "https://[2606:4700:4700::1111]/hook",
]
PRIVATE_URLS = [
    "http://127.0.0.1/", "http://127.1.2.3:8000/x", "http://localhost/", "http://LOCALHOST./", "http://api.localhost/",
    "http://169.254.169.254/latest/meta-data/", "http://10.0.0.5:6379/", "http://172.16.0.1/", "http://192.168.1.10/",
    "http://100.64.0.1/", "http://0.0.0.0/", "http://[::1]/", "http://[::ffff:127.0.0.1]/", "http://[fd00::1]/",
    "http://[fe80::1]/", "http://224.0.0.1/",
]
MALFORMED_URLS = [
    "", "   ", "example.com", "ftp://example.com/", "file:///etc/passwd", "gopher://example.com/", "javascript:alert(1)",
    "http://", "https://user:pass@example.com/", "https://user@example.com/", "http://example.com:99999/",
    "http://example.com:abc/", "https://example.com/" + "a" * 2100,
]


@pytest.fixture(autouse=True)
def _no_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "OUTBOUND_PRIVATE_HOST_ALLOWLIST", "")


@pytest.mark.parametrize("url", PUBLIC_URLS)
def test_public_urls_are_accepted(url):
    assert validate_outbound_url(url) == url


@pytest.mark.parametrize("url", PRIVATE_URLS + MALFORMED_URLS)
def test_private_and_malformed_urls_are_rejected(url):
    with pytest.raises(ValueError):
        validate_outbound_url(url)


def test_rejection_messages_never_echo_the_address():
    with pytest.raises(ValueError) as info:
        validate_outbound_url("http://10.9.8.7:6379/secret-path")
    assert "10.9.8.7" not in str(info.value) and "secret-path" not in str(info.value)


# ------------------------------------------------------------ the optional, empty-by-default allowlist


@pytest.mark.parametrize("entry, url", [
    ("10.0.0.5", "http://10.0.0.5:6379/"),
    ("10.0.0.0/8", "http://10.200.1.1/hook"),
    ("hooks.internal.corp", "http://hooks.internal.corp/x"),
    ("localhost", "http://localhost:9000/"),
    (" 192.168.0.0/16 , 10.1.1.1 ", "http://192.168.7.7/"),
    ("fd00::/8", "http://[fd00::5]/"),
])
def test_allowlist_permits_only_what_the_operator_listed(monkeypatch, entry, url):
    monkeypatch.setattr(settings, "OUTBOUND_PRIVATE_HOST_ALLOWLIST", entry)
    assert validate_outbound_url(url) == url


def test_allowlist_does_not_open_neighbouring_addresses(monkeypatch):
    monkeypatch.setattr(settings, "OUTBOUND_PRIVATE_HOST_ALLOWLIST", "10.0.0.5, 192.168.1.0/24")
    for url in ("http://10.0.0.6/", "http://192.168.2.1/", "http://127.0.0.1/", "http://169.254.169.254/"):
        with pytest.raises(ValueError):
            validate_outbound_url(url)


def test_allowlist_is_empty_by_default():
    assert type(settings).model_fields["OUTBOUND_PRIVATE_HOST_ALLOWLIST"].default == ""


# ------------------------------------------------------------ API surface


async def test_webhook_urls_are_validated_on_create_and_update(client, db_session, monkeypatch):
    (headers, org_id, _user), _other = await make_tenants(client, db_session, monkeypatch, "ssrf-wh")
    base = {"name": "hook", "events": ["message.created"]}
    for bad in ("http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:6379/", "http://localhost/", "ftp://example.com/", "http://10.0.0.5/"):
        response = await client.post(f"/organizations/{org_id}/webhooks", json={**base, "url": bad}, headers=headers)
        assert response.status_code == 422, (bad, response.text)
    created = await client.post(f"/organizations/{org_id}/webhooks", json={**base, "url": "https://example.com/hook"}, headers=headers)
    assert created.status_code == 200, created.text
    webhook_id = created.json()["id"]
    rejected = await client.patch(f"/webhooks/{webhook_id}", json={"url": "http://169.254.169.254/"}, headers=headers)
    assert rejected.status_code == 422
    accepted = await client.patch(f"/webhooks/{webhook_id}", json={"url": "https://example.org/other", "name": "renamed"}, headers=headers)
    assert accepted.status_code == 200 and accepted.json()["url"] == "https://example.org/other"
    untouched = await client.patch(f"/webhooks/{webhook_id}", json={"name": "renamed again"}, headers=headers)
    assert untouched.status_code == 200


async def test_mcp_server_urls_are_validated_on_create_and_update(client, db_session, monkeypatch):
    (headers, org_id, _user), _other = await make_tenants(client, db_session, monkeypatch, "ssrf-mcp")
    for transport in ("sse", "streamable_http"):
        for bad in ("http://169.254.169.254/", "http://localhost:8080/mcp", "http://10.0.0.7/mcp", "file:///etc/passwd"):
            response = await client.post(
                f"/organizations/{org_id}/mcp-servers", json={"name": "x", "transport": transport, "url": bad}, headers=headers,
            )
            assert response.status_code == 400, (transport, bad, response.text)
    created = await client.post(
        f"/organizations/{org_id}/mcp-servers", json={"name": "ok", "transport": "streamable_http", "url": "https://example.com/mcp"}, headers=headers,
    )
    assert created.status_code == 201, created.text
    server_id = created.json()["id"]
    rejected = await client.patch(f"/organizations/{org_id}/mcp-servers/{server_id}", json={"url": "http://127.0.0.1/"}, headers=headers)
    assert rejected.status_code == 400
    accepted = await client.patch(f"/organizations/{org_id}/mcp-servers/{server_id}", json={"url": "https://example.org/mcp"}, headers=headers)
    assert accepted.status_code == 200


# ------------------------------------------------------------ connection-time guard (webhook client)


class _Listener:
    """A real HTTP server on loopback that records every request it receives."""

    def __init__(self):
        outer = self
        self.hits = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                outer.hits.append(self.path)
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *args):
                return None

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def listener():
    server = _Listener()
    yield server
    server.close()


def test_a_webhook_never_reaches_a_loopback_listener(listener):
    with safe_webhook_client(timeout=5) as http, pytest.raises(OutboundURLError):
        http.post(f"http://127.0.0.1:{listener.port}/hook", json={"x": 1})
    assert listener.hits == []


def test_a_hostname_resolving_to_loopback_is_refused_at_connection_time(listener, monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda host, port, **kw: [(2, 1, 6, "", ("127.0.0.1", port))])
    with safe_webhook_client(timeout=5) as http, pytest.raises(OutboundURLError):
        http.post(f"http://innocent.example:{listener.port}/hook", json={})
    assert listener.hits == []


@pytest.mark.parametrize("resolved", ["10.0.0.5", "169.254.169.254", "192.168.1.1", "172.16.5.5", "100.64.0.9", "0.0.0.0", "::1", "fd00::1", "::ffff:127.0.0.1"])
def test_every_non_public_resolution_is_refused(monkeypatch, resolved):
    monkeypatch.setattr("socket.getaddrinfo", lambda host, port, **kw: [(2, 1, 6, "", (resolved, port))])
    with safe_webhook_client(timeout=5) as http, pytest.raises(OutboundURLError):
        http.post("http://innocent.example/hook", json={})


def test_dns_rebinding_is_refused_on_the_second_resolution(monkeypatch):
    """The first lookup is public (it would pass any one-off validation), the next one is the metadata service."""
    answers = iter(["93.184.216.34", "169.254.169.254"])
    monkeypatch.setattr("socket.getaddrinfo", lambda host, port, **kw: [(2, 1, 6, "", (next(answers), port))])
    connected = []

    def fake_connect(self, host, port, timeout=None, local_address=None, socket_options=None):
        connected.append(host)
        raise httpcore.ConnectError("stop here")

    monkeypatch.setattr("httpcore._backends.sync.SyncBackend.connect_tcp", fake_connect)
    with safe_webhook_client(timeout=5) as http:
        with pytest.raises(httpx.ConnectError):
            http.post("http://rebind.example/hook", json={})
        with pytest.raises(OutboundURLError):
            http.post("http://rebind.example/hook", json={})
    assert connected == ["93.184.216.34"]  # the socket is opened to the validated address, never to the hostname


def test_a_public_destination_is_connected_by_its_resolved_address(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda host, port, **kw: [(2, 1, 6, "", ("93.184.216.34", port))])
    seen = {}

    def fake_connect(self, host, port, timeout=None, local_address=None, socket_options=None):
        seen.update(host=host, port=port)
        raise httpcore.ConnectError("stop here")

    monkeypatch.setattr("httpcore._backends.sync.SyncBackend.connect_tcp", fake_connect)
    with safe_webhook_client(timeout=5) as http, pytest.raises(httpx.ConnectError):
        http.post("https://example.com/hook", json={})
    assert seen == {"host": "93.184.216.34", "port": 443}


def test_webhook_client_does_not_follow_redirects():
    with safe_webhook_client(timeout=5) as http:
        assert http.follow_redirects is False


def test_the_allowlist_lets_a_self_hosted_receiver_through(listener, monkeypatch):
    monkeypatch.setattr(settings, "OUTBOUND_PRIVATE_HOST_ALLOWLIST", "127.0.0.1")
    with safe_webhook_client(timeout=5) as http:
        response = http.post(f"http://127.0.0.1:{listener.port}/hook", json={"x": 1})
    assert response.status_code == 200 and listener.hits == ["/hook"]


def test_the_allowlist_never_opens_other_private_addresses(listener, monkeypatch):
    monkeypatch.setattr(settings, "OUTBOUND_PRIVATE_HOST_ALLOWLIST", "10.0.0.5")
    with safe_webhook_client(timeout=5) as http, pytest.raises(OutboundURLError):
        http.post(f"http://127.0.0.1:{listener.port}/hook", json={})
    assert listener.hits == []


# ------------------------------------------------------------ what is persisted and shown to the tenant


def test_error_descriptions_are_fixed_texts_without_addresses_or_remote_output():
    leaky = [
        httpx.ConnectError("[Errno 111] Connection refused to 10.0.0.5:6379"),
        httpx.ReadTimeout("timed out talking to 169.254.169.254"),
        OSError("[WinError 10061] 10.1.2.3 refused"),
        RuntimeError("redis password is hunter2"),
        ExceptionGroup("unhandled errors in a TaskGroup", [OutboundURLError("destination is not a public address")]),  # noqa: F821 -- builtin since 3.11
        httpx.HTTPStatusError("status 500: {internal stack trace}", request=MagicMock(), response=MagicMock()),
    ]
    descriptions = [describe_outbound_error(exc) for exc in leaky]
    assert descriptions == [
        "connection failed", "request timed out", "connection failed", "request failed",
        "destination not allowed (not a public address)", "remote server answered with an error status",
    ]
    joined = " ".join(descriptions)
    for secret in ("10.0.0.5", "169.254", "hunter2", "stack trace", "6379"):
        assert secret not in joined


def _delivery_task_world(monkeypatch, client_factory, retry_count=0):
    from api.tasks import webhooks as webhook_tasks

    webhook = SimpleNamespace(id="w1", is_active=True, headers={}, url="https://example.com/hook", timeout=5, retry_count=retry_count, secret=None)
    delivery = SimpleNamespace(id="d1", webhook_id="w1", event="message.created", payload={"a": 1}, attempt=0, error=None, status_code=None, response_body=None, delivered_at=None)

    class _Session:
        def __init__(self, engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, model, key):
            return delivery if key == "d1" else webhook

        def commit(self):
            return None

    monkeypatch.setattr(webhook_tasks, "SyncSession", _Session)
    monkeypatch.setattr(webhook_tasks, "decrypt_webhook_secret", lambda hook: None)
    monkeypatch.setattr(webhook_tasks, "safe_webhook_client", client_factory)
    return webhook_tasks, delivery


def test_the_delivery_task_stores_a_fixed_error_not_the_exception_text(monkeypatch):
    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, *args, **kwargs):
            raise httpx.ConnectError("All connection attempts failed: 10.0.0.5:6379 (redis)")

    webhook_tasks, delivery = _delivery_task_world(monkeypatch, lambda timeout: _Client())
    webhook_tasks.deliver_webhook_task.run("d1")
    assert delivery.error == "connection failed"
    assert "10.0.0.5" not in delivery.error and delivery.status_code is None


def test_the_delivery_task_reports_a_blocked_destination_with_a_fixed_text(monkeypatch):
    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, *args, **kwargs):
            raise OutboundURLError("destination is not a public address")

    webhook_tasks, delivery = _delivery_task_world(monkeypatch, lambda timeout: _Client())
    webhook_tasks.deliver_webhook_task.run("d1")
    assert delivery.error == "destination not allowed (not a public address)"
    assert delivery.delivered_at is None


def test_the_delivery_task_still_delivers_and_records_a_successful_response(monkeypatch):
    class _Response:
        status_code = 204
        text = ""
        request = None

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, url, json=None, headers=None):
            assert url == "https://example.com/hook" and json == {"a": 1}
            assert headers["X-Webhook-Event"] == "message.created"
            return _Response()

    webhook_tasks, delivery = _delivery_task_world(monkeypatch, lambda timeout: _Client())
    webhook_tasks.deliver_webhook_task.run("d1")
    assert delivery.status_code == 204 and delivery.error is None and delivery.delivered_at is not None


# ------------------------------------------------------------ MCP transports


def _mcp_server(transport, url):
    return MCPServerConfig(name="probe", transport=transport, url=url, auth_type="none")


@pytest.mark.parametrize("transport", ["sse", "streamable_http"])
@pytest.mark.parametrize("url", ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:6379/", "http://localhost/mcp"])
async def test_mcp_refuses_private_urls_stored_before_the_fix(transport, url):
    with pytest.raises(MCPClientError) as info:
        await discover_tools(_mcp_server(transport, url))
    assert "not allowed" in str(info.value)
    assert "169.254" not in str(info.value) and "6379" not in str(info.value)


@pytest.mark.parametrize("transport", ["sse", "streamable_http"])
async def test_mcp_refuses_a_hostname_that_resolves_to_a_private_address(monkeypatch, transport):
    monkeypatch.setattr("socket.getaddrinfo", lambda host, port, **kw: [(2, 1, 6, "", ("10.0.0.7", port))])
    with pytest.raises(MCPClientError) as info:
        await discover_tools(_mcp_server(transport, "http://innocent.example/mcp"))
    assert str(info.value).endswith("destination not allowed (not a public address)")
    assert "10.0.0.7" not in str(info.value)


def test_the_mcp_http_client_is_wired_to_the_resolution_guard():
    """Guards the private httpx2/httpcore2 attribute this relies on: if a dependency upgrade moves it, this fails loudly."""
    import asyncio

    async def build():
        async with mcp_http_client() as client:
            return type(client._transport._pool._network_backend).__name__, client.follow_redirects

    assert asyncio.run(build()) == ("_SafeAsyncBackend", True)
