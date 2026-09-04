"""
Partie 2.1.10 -- real SSRF-safe URL fetching tests
(api/services/url_fetching.py), fast tier. `validate_url` is pure,
no-network format validation. The SSRF-blocking tests below call the
real async fetch/validation functions against literal loopback/
private/link-local IP addresses -- these resolve INSTANTLY via a local
`getaddrinfo` call (no real network round-trip, matching the "no real
network call in the fast suite" convention every other test file here
follows) and are refused at the connection layer before any real
socket opens, so they exercise the REAL blocking logic end to end, not
a mock of it. The real "happy path" tests that reach an actual external
URL live in tests/test_url_fetching_integration.py instead.
"""

import datetime as dt

import httpx
import pytest

from api.services.url_fetching import fetch_url_content, get_url_last_modified, validate_url, validate_url_accessibility


# ------------------------------------------------------- validate_url --

def test_validate_url_accepts_real_http_and_https_urls():
    assert validate_url("https://example.com/page") == "https://example.com/page"
    assert validate_url("http://example.com/page") == "http://example.com/page"


@pytest.mark.parametrize("bad_url", [
    "ftp://example.com/",
    "file:///etc/passwd",
    "not-a-url",
    "gopher://example.com/",
    "data:text/html,<script>alert(1)</script>",
    "",
])
def test_validate_url_rejects_disallowed_or_missing_schemes(bad_url):
    """Vision critique Q2 -- only http/https are ever allowed."""
    with pytest.raises(ValueError):
        validate_url(bad_url)


def test_validate_url_rejects_embedded_credentials():
    """A real, documented URL-parsing confusion vector -- confirmed for
    real that pydantic's own HttpUrl (used at the schema layer,
    api/schemas/documents.py's DocumentUrlImportRequest) does NOT
    reject this, so this module's own check is not redundant."""
    with pytest.raises(ValueError):
        validate_url("http://user:pass@example.com/")


def test_validate_url_rejects_a_url_with_no_hostname():
    with pytest.raises(ValueError):
        validate_url("http:///no-host")


# ------------------------------------------------- SSRF protection (real) --

@pytest.mark.parametrize("blocked_url", [
    "http://127.0.0.1:1/",
    "http://localhost:1/",
    "http://169.254.169.254/latest/meta-data/",  # the real cloud metadata endpoint
    "http://[::1]:1/",
    "http://10.0.0.1:1/",
    "http://192.168.1.1:1/",
    "http://0.0.0.0:1/",
])
async def test_validate_url_accessibility_blocks_private_and_loopback_targets(blocked_url):
    """Vision critique Q2's own real answer -- confirmed for real that
    the connection is refused BEFORE any real socket is opened (see
    api/services/url_fetching.py's own module docstring for the full
    real design: a custom httpcore network backend resolving and
    validating the IP itself, not a hostname-string blocklist)."""
    with pytest.raises(ValueError):
        await validate_url_accessibility(blocked_url)


async def test_fetch_url_content_blocks_private_targets_too():
    """The SSRF-safe transport is ONE shared configuration -- confirmed
    for real that fetch_url_content is protected the same way
    validate_url_accessibility is, not by a second, independently
    built client that could forget it."""
    with pytest.raises(ValueError):
        await fetch_url_content("http://127.0.0.1:1/")


# ------------------------------------------------- get_url_last_modified --

async def test_get_url_last_modified_never_raises_for_an_ssrf_blocked_target():
    """Vision critique 3 (Partie 2.2.13) -- même une cible réellement
    bloquée (SSRF) ne doit jamais faire planter un check périodique,
    contrairement à validate_url_accessibility/fetch_url_content qui
    lèvent délibérément ValueError -- cette fonction-ci a le contrat
    inverse ("never raises"), donc ce même ValueError doit être
    absorbé, pas laissé remonter."""
    result = await get_url_last_modified("http://127.0.0.1:1/")
    assert result is None


async def test_get_url_last_modified_parses_a_real_last_modified_header(monkeypatch):
    """Validation criterion -- le header HTTP standard est lu et
    parsé correctement (real httpx flow, fake transport -- same "real
    library behavior, fake network" split as every other real-network
    dependency in this codebase)."""
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Last-Modified": "Wed, 21 Oct 2015 07:28:00 GMT"})

    monkeypatch.setattr("api.services.url_fetching._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(_handler)))

    result = await get_url_last_modified("https://example.com/report.pdf")
    assert result == dt.datetime(2015, 10, 21, 7, 28, 0, tzinfo=dt.timezone.utc)


async def test_get_url_last_modified_returns_none_when_the_header_is_absent(monkeypatch):
    """Validation criterion -- un serveur qui n'envoie honnêtement pas
    ce header (un cas réel et courant) ne doit jamais produire une
    date fabriquée."""
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    monkeypatch.setattr("api.services.url_fetching._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(_handler)))

    assert await get_url_last_modified("https://example.com/") is None


async def test_get_url_last_modified_returns_none_for_an_unparseable_header(monkeypatch):
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Last-Modified": "not a real http-date"})

    monkeypatch.setattr("api.services.url_fetching._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(_handler)))

    assert await get_url_last_modified("https://example.com/") is None


async def test_get_url_last_modified_returns_none_for_a_non_200_response(monkeypatch):
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    monkeypatch.setattr("api.services.url_fetching._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(_handler)))

    assert await get_url_last_modified("https://example.com/gone.pdf") is None
