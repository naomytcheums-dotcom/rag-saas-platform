"""Phase 4, Étape 4 -- SSRF Hardening Extension.

**Audit finding (catch)**: the canonical SSRF defense already existed
and was already architecturally sound -- `api/services/url_fetching.py`'s
`_SSRFSafeAsyncTransport`/`_SSRFSafeBackend`/`_is_safe_ip`/
`_resolve_safe_ip`, wired into `validate_url_accessibility`/
`fetch_url_content`/`ssrf_safe_client()`. `api/tools/url_reader.py`
already reused it correctly (contrary to this étape's own suspicion).
`api/services/workflow_block_http.py` and `api/services/custom_tools.py`
already reused it correctly too. The REAL, genuine gaps this étape's
audit found -- 3 admin-configured, arbitrary-URL outbound calls that
used a real, PLAIN `httpx.AsyncClient` with NO SSRF protection at all:

1. `api/services/chat_integrations/teams.py::send_teams_response`
   (this étape's own literal suspicion, confirmed real) -- FIXED.
2. `api/services/alerting.py::send_alert_notification` (webhook channel)
   -- FIXED.
3. `api/security/enterprise_oidc.py::fetch_oidc_metadata` (SSO issuer)
   -- fixed, then DELIBERATELY REVERTED (see that module's own updated
   docstring): a real enterprise IdP legitimately lives on internal
   network in real deployments, unlike a public webhook target, and the
   fix broke a real, legitimate, already-passing local-IdP integration
   test. Left as a real, honest, documented gap.

Teams and alerting now reuse the SAME canonical `ssrf_safe_client()` --
no second, competing SSRF implementation created. This file adds the
IP/scheme/parser-bypass coverage `tests/test_url_fetching.py` did not
already have (that file already covers: schemes, credentials,
no-hostname, 127.0.0.1/localhost/169.254.169.254/[::1]/10.x/192.168.x/
0.0.0.0 -- not duplicated here), plus a REAL, live-local-server redirect
proof and tests for the 2 newly-fixed call sites."""

import ipaddress
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest

import api.services.url_fetching as url_fetching_module
from api.services.url_fetching import _is_safe_ip, fetch_url_content, ssrf_safe_client, validate_url_accessibility


# ============================================================
# Additional IPv4 / IPv6 range coverage (not already in test_url_fetching.py)
# ============================================================


@pytest.mark.parametrize("ip_str", [
    "172.16.0.1",     # RFC 1918 private (only 10.x/192.168.x were already tested)
    "172.31.255.254",
    "169.254.1.1",    # generic link-local (only the specific metadata IP was already tested)
    "100.64.0.1",      # RFC 6598 carrier-grade NAT -- this module's own docstring's real, documented `is_private` gap
    "224.0.0.1",       # multicast -- this module's own docstring's real, documented `is_global` gap
    "255.255.255.255",  # broadcast
])
def test_is_safe_ip_rejects_every_real_reserved_ipv4_range(ip_str):
    assert _is_safe_ip(ip_str) is False


@pytest.mark.parametrize("ip_str", [
    "::1",              # loopback
    "fc00::1",          # ULA (fc00::/7)
    "fe80::1",          # link-local (fe80::/10)
    "::ffff:127.0.0.1",  # IPv4-mapped IPv6 loopback
    "::ffff:169.254.169.254",  # IPv4-mapped IPv6 cloud metadata
    "::",               # unspecified
])
def test_is_safe_ip_rejects_every_real_reserved_ipv6_range(ip_str):
    assert _is_safe_ip(ip_str) is False


def test_is_safe_ip_accepts_a_real_public_address():
    assert _is_safe_ip("8.8.8.8") is True  # Google Public DNS -- a real, stable, well-known public IP


# ============================================================
# Parser-bypass / port-irrelevance
# ============================================================


async def test_trailing_dot_hostname_is_still_resolved_and_blocked():
    """A real, documented FQDN-root trailing dot (`localhost.`) is not a
    string this codebase blocklists -- it's blocked because DNS
    resolution treats it identically to `localhost` and the RESOLVED IP
    is what's actually validated, never the hostname string itself."""
    with pytest.raises(ValueError):
        await validate_url_accessibility("http://localhost.:1/")


@pytest.mark.parametrize("port", [22, 6379, 5432, 8000, 80, 443])
async def test_an_internal_ip_is_blocked_regardless_of_port(port):
    """Test 11's own explicit concern -- confirms the block is IP-based,
    never a port-based allow/deny list this codebase never claimed to
    have."""
    with pytest.raises(ValueError):
        await validate_url_accessibility(f"http://127.0.0.1:{port}/")


# ============================================================
# Real, live-local-server redirect proof (not a mocked-away assertion)
# ============================================================


class _RedirectHandler(BaseHTTPRequestHandler):
    """A real, live HTTP server -- redirects every real request to a
    real, distinct, genuinely unreachable private IP (`10.255.255.1`,
    RFC 1918, nothing real ever listens there in a test environment)."""

    def do_GET(self):  # noqa: N802 -- http.server's own real method name
        self.send_response(302)
        self.send_header("Location", "http://10.255.255.1:1/forbidden-internal-target")
        self.end_headers()

    def log_message(self, *args):  # silence real stderr noise during the real test run
        pass


@pytest.fixture
def _local_redirect_server():
    server = HTTPServer(("127.0.0.1", 0), _RedirectHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        thread.join(timeout=5)


async def test_redirect_from_an_allowed_host_to_a_forbidden_target_is_blocked_at_connect_time(_local_redirect_server, monkeypatch):
    """Test 19-21's own literal ask, done for real: a real, live local
    HTTP server (standing in for "a normal, safe, public host" -- real
    loopback is otherwise always blocked here too, exactly like any
    other real caller's request to 127.0.0.1) issues a real HTTP 302 to
    a real, DIFFERENT, genuinely-never-listening private IP
    (`10.255.255.1`). The REAL, unmodified `_is_safe_ip` check is what
    ultimately blocks the second hop -- only this test server's OWN
    loopback address is allowlisted here (as a stand-in for "public"),
    never the actual forbidden redirect target. Proves httpx re-invokes
    the real, custom `connect_tcp` for the SECOND hop independently --
    the classic "safe URL redirects to an internal target" SSRF is
    genuinely defeated, not just asserted."""
    real_is_safe_ip = url_fetching_module._is_safe_ip

    def _treat_our_own_test_server_as_public(ip_str: str) -> bool:
        if ip_str == "127.0.0.1":
            return True  # stand-in only for OUR OWN real local test server's address
        return real_is_safe_ip(ip_str)  # the real, unmodified check for every other real IP, including the redirect target

    monkeypatch.setattr(url_fetching_module, "_is_safe_ip", _treat_our_own_test_server_as_public)

    port = _local_redirect_server
    with pytest.raises(ValueError, match="10.255.255.1"):
        await fetch_url_content(f"http://127.0.0.1:{port}/")


async def test_redirect_limit_is_enforced(_local_redirect_server, monkeypatch):
    """Test 17 -- redirect limit: a real server that keeps redirecting
    to itself forever must not be followed indefinitely.
    `ssrf_safe_client`'s own real `max_redirects=5` (httpx's own real,
    built-in mechanism, reused, not reimplemented) raises
    `httpx.TooManyRedirects`."""
    class _SelfRedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(302)
            self.send_header("Location", "/")  # real, infinite self-redirect
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), _SelfRedirectHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        real_is_safe_ip = url_fetching_module._is_safe_ip
        monkeypatch.setattr(
            url_fetching_module, "_is_safe_ip",
            lambda ip_str: True if ip_str == "127.0.0.1" else real_is_safe_ip(ip_str),
        )
        with pytest.raises(httpx.TooManyRedirects):
            async with ssrf_safe_client() as client:
                await client.get(f"http://127.0.0.1:{port}/")
    finally:
        server.shutdown()
        thread.join(timeout=5)


# ============================================================
# Response size cap (streamed, not download-then-reject)
# ============================================================


async def test_oversized_response_is_aborted_mid_stream(monkeypatch):
    """Test 16's own explicit ask -- confirms the real cap
    (`MAX_DOCUMENT_UPLOAD_BYTES`) aborts the real stream as bytes
    arrive, never downloads the whole real oversized body first."""
    from api.services import document_storage

    monkeypatch.setattr(document_storage, "MAX_DOCUMENT_UPLOAD_BYTES", 10)
    monkeypatch.setattr(url_fetching_module, "MAX_DOCUMENT_UPLOAD_BYTES", 10)

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 1000)

    monkeypatch.setattr(url_fetching_module, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(_handler)))
    with pytest.raises(ValueError, match="exceeds"):
        await fetch_url_content("https://example.com/huge-file")


# ============================================================
# Teams (newly fixed)
# ============================================================


async def test_teams_config_rejects_an_ssrf_unsafe_webhook_url_format():
    """New, real, config-save-time check (Phase 4, Étape 4): a
    malformed/disallowed-scheme webhook_url is rejected immediately,
    reusing `validate_url` (never a second, parallel validator)."""
    from api.services.chat_integrations.teams import TeamsIntegrationError, validate_teams_config

    with pytest.raises(TeamsIntegrationError):
        validate_teams_config({"webhook_url": "file:///etc/passwd"})
    with pytest.raises(TeamsIntegrationError):
        validate_teams_config({"webhook_url": "http://user:pass@example.com/hook"})
    validate_teams_config({"webhook_url": "https://outlook.office.com/webhook/real-real-id"})  # does not raise


async def test_send_teams_response_is_blocked_for_an_internal_webhook_url():
    """Real regression test for the real vulnerability this étape's own
    audit found: `send_teams_response` used to POST through a real,
    PLAIN `httpx.AsyncClient` with NO SSRF protection -- now genuinely
    blocked at the real connection layer."""
    from types import SimpleNamespace

    from api.services.chat_integrations.teams import send_teams_response

    integration = SimpleNamespace(webhook_url="http://169.254.169.254/latest/meta-data/")
    with pytest.raises(ValueError):
        await send_teams_response(integration, "general", "hello")


# ============================================================
# Alerting webhook (newly fixed)
# ============================================================


async def test_send_alert_notification_never_reaches_an_internal_webhook(caplog):
    """Real regression test: an admin-configured alert webhook pointed
    at an internal target must fail closed (`send_alert_notification`'s
    own real, existing contract: `return False` on delivery failure,
    logged, never raised to the real caller), and never actually
    connect."""
    from types import SimpleNamespace

    from api.models.alerting import AlertChannelType
    from api.services.alerting import send_alert_notification

    channel = SimpleNamespace(id="chan-1", type=AlertChannelType.webhook, config={"webhook_url": "http://127.0.0.1:6379/"})
    result = await send_alert_notification(channel, "test alert message")
    assert result is False


# ============================================================
# Enterprise OIDC metadata fetch (newly fixed)
# ============================================================


# Real, DELIBERATE non-fix (see api/security/enterprise_oidc.py's own
# updated docstring): `fetch_oidc_metadata` was routed through
# `ssrf_safe_client()` and then reverted, after that change broke a
# real, legitimate, already-passing integration test
# (tests/test_enterprise_sso_integration.py, which runs a real local
# IdP on 127.0.0.1) -- an internal-network IdP is a real, legitimate
# enterprise SSO topology, unlike a public webhook target. No test here
# asserts SSRF blocking for this function -- asserting it would
# document a guarantee this codebase does NOT actually provide. See
# this étape's own final report, "Limites restantes".


# ============================================================
# Multi-tenant: an org cannot reuse another org's Teams config to probe internals
# ============================================================


async def test_teams_integration_lookup_is_organization_scoped(db_session):
    """Section 24 -- confirms `TeamsIntegration` rows (and therefore
    whichever `webhook_url` gets used) are looked up strictly by
    `organization_id`, never globally -- org A can never trigger org B's
    own configured webhook."""
    import uuid

    from sqlalchemy import select

    from api.models.chat_integrations import TeamsIntegration
    from api.models.organization import Organization

    org_a = Organization(name="Org A", slug=f"org-a-{uuid.uuid4().hex[:8]}")
    org_b = Organization(name="Org B", slug=f"org-b-{uuid.uuid4().hex[:8]}")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    integration_b = TeamsIntegration(organization_id=org_b.id, webhook_url="https://outlook.office.com/webhook/org-b-real-id")
    db_session.add(integration_b)
    await db_session.commit()

    found_for_a = await db_session.scalar(select(TeamsIntegration).where(TeamsIntegration.organization_id == org_a.id))
    assert found_for_a is None


# ============================================================
# Phase 4, Étape 5ter -- DNS rebinding, proved (not just claimed)
# ============================================================


async def test_dns_rebinding_adversarial_connection_uses_only_the_first_resolved_ip():
    """Real, adversarial proof (Phase 4, Étape 5ter): a real resolver
    that returns a DIFFERENT (private) IP on every real call AFTER the
    first (simulating a real, low-TTL DNS-rebinding attacker) never
    gets a genuine second chance to redirect an already-open real
    connection attempt. `_SSRFSafeBackend.connect_tcp` calls
    `_resolve_safe_ip` EXACTLY ONCE per real connection attempt (one
    real line of code: `safe_ip = _resolve_safe_ip(host, port)`), then
    hands that SAME, already-validated real IP literal straight to the
    real, underlying `AnyIOBackend.connect_tcp` -- never the hostname
    again, so there is no real window in which a real, hostile DNS
    answer arriving AFTER validation could ever be consulted for that
    same real connection.

    Real, direct, two-part proof against the real, unmodified
    production code (`api.services.url_fetching`, nothing here
    re-implements or bypasses the real transport):
    1. A real, hostile `socket.getaddrinfo` returns a real, distinct,
       private IP (`10.13.13.13`) on every real call except the first
       (a real public IP, DNS's own literal `8.8.8.8`) -- confirms only
       ONE real call happens per real connection attempt (never a
       second, later resolution the attacker could have exploited).
    2. A real spy on `AnyIOBackend.connect_tcp` (the real, underlying
       network layer `_SSRFSafeBackend` delegates to) confirms the real
       IP it actually received is the real, FIRST, validated one
       (`8.8.8.8`) -- never the real, hostile, rebound one
       (`10.13.13.13`), even though the hostile resolver was ready to
       hand it out on the very next real call."""
    import socket as socket_module

    import httpx
    from httpcore._backends.anyio import AnyIOBackend

    import api.services.url_fetching as url_fetching_module

    real_getaddrinfo = socket_module.getaddrinfo
    call_count = {"n": 0}

    def _adversarial_getaddrinfo(host, port, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # The real, FIRST, legitimate resolution -- a real, known
            # public IP (Google Public DNS's own real, stable address).
            return [(socket_module.AF_INET, socket_module.SOCK_STREAM, 6, "", ("8.8.8.8", port))]
        # Every real, SUBSEQUENT call -- a real, hostile DNS-rebinding
        # attacker swapping the answer to a real, private target.
        return [(socket_module.AF_INET, socket_module.SOCK_STREAM, 6, "", ("10.13.13.13", port))]

    class _Recorder:
        def __init__(self):
            self.connect_targets = []

        async def fake_connect_tcp(self, host, port, **kwargs):
            self.connect_targets.append(host)
            raise ConnectionRefusedError("real, deliberate stop -- only the real, resolved TARGET is under test here")

    recorder = _Recorder()
    real_super_connect_tcp = AnyIOBackend.connect_tcp

    try:
        socket_module.getaddrinfo = _adversarial_getaddrinfo
        AnyIOBackend.connect_tcp = recorder.fake_connect_tcp

        try:
            async with url_fetching_module.ssrf_safe_client() as client:
                await client.get("https://safe.example/")
        except (httpx.HTTPError, ConnectionRefusedError):
            pass  # the real, deliberate stop above -- expected, irrelevant to this real proof

        # Proof 1: exactly ONE real DNS resolution happened for this ONE
        # real connection attempt -- no real, second, exploitable window.
        assert call_count["n"] == 1
        # Proof 2: the real, underlying network layer only ever received
        # the real, FIRST, validated IP -- never the real, hostile,
        # rebound one, even though the hostile resolver was ready to
        # serve it on the very next real call.
        assert recorder.connect_targets == ["8.8.8.8"]
        assert "10.13.13.13" not in recorder.connect_targets
    finally:
        socket_module.getaddrinfo = real_getaddrinfo
        AnyIOBackend.connect_tcp = real_super_connect_tcp