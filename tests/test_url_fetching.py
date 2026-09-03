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

import pytest

from api.services.url_fetching import fetch_url_content, validate_url, validate_url_accessibility


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
