"""
Partie 2.1.10 -- real network tests for api/services/url_fetching.py.
Unlike tests/test_url_fetching.py (whose SSRF-blocking tests never
reach the real network at all), these actually reach a real, external,
deliberately stable target: `example.com`, IANA's own domain reserved
by RFC 2606 specifically for documentation/testing use, chosen instead
of some other real site precisely so this test suite is never mistaken
for a crawler hitting a real production service.
"""

from api.services.url_fetching import fetch_url_content, validate_url_accessibility, validate_url_robots_txt


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
