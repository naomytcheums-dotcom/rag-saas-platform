"""
Partie 2.1.11 -- real network test for api/services/sitemap_extraction.py's
own fetch_sitemap. Same reasoning as tests/test_url_fetching_integration.py:
this reaches a real, external target, so it's kept out of the fast tier.

Unlike url_fetching_integration.py, this can't use example.com (it serves
no real sitemap) -- sitemaps.org's own sitemap.xml, at the domain that
DEFINES the sitemap protocol itself, is used instead: a real, stable,
non-index urlset, confirmed reachable and non-index via the ad-hoc smoke
test that verified this module's own orchestration logic before this
formal suite was written.
"""

from api.services.sitemap_extraction import fetch_sitemap, is_sitemap_index, parse_sitemap


async def test_fetch_sitemap_downloads_and_parses_a_real_external_sitemap():
    """Validation criterion: l'import de sitemap fonctionne, le parsing
    du sitemap fonctionne -- against a real, external, non-mocked
    target."""
    content = await fetch_sitemap("https://www.sitemaps.org/sitemap.xml")
    assert is_sitemap_index(content) is False
    urls = parse_sitemap(content)
    assert len(urls) > 0
    assert all(url.startswith("http") for url in urls)
