"""
Partie 2.1.10 -- real network tests for api/services/url_fetching.py.
Unlike tests/test_url_fetching.py (whose SSRF-blocking tests never
reach the real network at all), these actually reach a real, external,
deliberately stable target: `example.com`, IANA's own domain reserved
by RFC 2606 specifically for documentation/testing use, chosen instead
of some other real site precisely so this test suite is never mistaken
for a crawler hitting a real production service.
"""

import datetime as dt

from api.services.url_fetching import fetch_url_content, get_url_last_modified, validate_url_accessibility, validate_url_robots_txt


async def test_validate_url_accessibility_accepts_a_real_reachable_page():
    """Validation criterion: a real, valid, reachable URL is accepted --
    does not raise."""
    await validate_url_accessibility("https://example.com")


async def test_fetch_url_content_returns_real_bytes_and_the_real_final_url():
    """Validation criterion: real content is actually downloaded, and
    the real final URL (after any redirects) is reported, not
    necessarily the one originally requested."""
    content, final_url = await fetch_url_content("https://example.com")
    assert b"example" in content.lower()
    assert final_url.startswith("https://example.com")


async def test_validate_url_robots_txt_does_not_block_a_real_page_with_no_disallow():
    """Real, best-effort robots.txt handling -- example.com serves no
    robots.txt disallowing this importer, confirmed for real, so this
    must not raise."""
    await validate_url_robots_txt("https://example.com/")


async def test_get_url_last_modified_against_a_real_reachable_page():
    """Partie 2.2.13 -- a real HEAD request against a real, stable
    target. Deliberately does NOT assert whether example.com happens to
    send a real Last-Modified header today (real CDN-served pages vary,
    and can change this without notice -- the same honest "don't force
    a flaky assertion on a fact this codebase doesn't control" reasoning
    already established elsewhere, e.g. Partie 2.1.18's own OneDrive
    integration test) -- only that a real request against a real,
    reachable URL never raises, and that IF a value comes back, it's a
    real, timezone-aware datetime."""
    result = await get_url_last_modified("https://example.com")
    assert result is None or isinstance(result, dt.datetime) and result.tzinfo is not None
