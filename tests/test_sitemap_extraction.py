"""
Partie 2.1.11 -- real sitemap parsing tests (api/services/sitemap_extraction.py),
fast tier. `parse_sitemap`/`parse_sitemap_index`/`is_sitemap_index`/
`filter_sitemap_urls`/`validate_sitemap_url` are all pure, no-network
logic. `fetch_sitemap`'s own gzip-decompression logic is tested here
too, with the real, SSRF-safe network fetch it wraps
(`api/services/url_fetching.py`'s `fetch_url_content`) monkeypatched
out -- that real network call is already covered by
tests/test_url_fetching.py/test_url_fetching_integration.py, and
re-verifying it here would just be redundant, real-network-dependent
weight in the fast suite. The real end-to-end fetch (network included)
lives in tests/test_sitemap_extraction_integration.py instead.
"""

import gzip
from unittest.mock import AsyncMock, patch

import pytest
from lxml import etree

from api.services.sitemap_extraction import (
    fetch_sitemap,
    filter_sitemap_urls,
    is_sitemap_index,
    parse_sitemap,
    parse_sitemap_index,
    validate_sitemap_url,
)

_REAL_URLSET = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/blog/post-1</loc><lastmod>2026-01-01</lastmod></url>
  <url><loc>https://example.com/blog/post-2</loc></url>
  <url><loc>https://example.com/about</loc></url>
</urlset>"""

_REAL_SITEMAPINDEX = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sitemap2.xml</loc></sitemap>
</sitemapindex>"""

_NO_NAMESPACE_URLSET = b"<urlset><url><loc>https://example.com/no-ns</loc></url></urlset>"

_MALFORMED_XML = b"<urlset><url><loc>https://example.com/broken</urlset>"


# ------------------------------------------------------- validate_sitemap_url --

def test_validate_sitemap_url_accepts_a_real_url():
    """Validation criterion -- reuses Partie 2.1.10's own real
    validate_url directly (no extra real constraint exists -- the
    sitemaps.org protocol places none on a sitemap's own url)."""
    assert validate_sitemap_url("https://example.com/sitemap.xml") == "https://example.com/sitemap.xml"


def test_validate_sitemap_url_rejects_a_disallowed_scheme():
    with pytest.raises(ValueError):
        validate_sitemap_url("ftp://example.com/sitemap.xml")


# --------------------------------------------------------- parse_sitemap --

def test_parse_sitemap_extracts_every_real_page_url():
    """Validation criterion -- every real <loc> in a real, namespaced
    <urlset> is extracted."""
    assert parse_sitemap(_REAL_URLSET) == [
        "https://example.com/blog/post-1",
        "https://example.com/blog/post-2",
        "https://example.com/about",
    ]


def test_parse_sitemap_works_without_a_declared_namespace_too():
    """Real finding: some real-world sitemaps omit the namespace
    declaration (technically non-conformant) -- confirmed for real
    that local-name()-based extraction tolerates this rather than
    silently returning nothing."""
    assert parse_sitemap(_NO_NAMESPACE_URLSET) == ["https://example.com/no-ns"]


def test_parse_sitemap_raises_for_malformed_xml():
    with pytest.raises(etree.XMLSyntaxError):
        parse_sitemap(_MALFORMED_XML)


# --------------------------------------------------- parse_sitemap_index --

def test_parse_sitemap_index_extracts_every_real_sub_sitemap_url():
    """Validation criterion -- sub-sitemaps are extracted from a real
    <sitemapindex>."""
    assert parse_sitemap_index(_REAL_SITEMAPINDEX) == [
        "https://example.com/sitemap1.xml",
        "https://example.com/sitemap2.xml",
    ]


# ------------------------------------------------------- is_sitemap_index --

def test_is_sitemap_index_distinguishes_the_two_real_root_shapes():
    """Validation criterion -- sub-sitemaps ARE correctly handled,
    starting with correctly telling the two real sitemap document
    shapes apart."""
    assert is_sitemap_index(_REAL_URLSET) is False
    assert is_sitemap_index(_REAL_SITEMAPINDEX) is True


# ----------------------------------------------------- filter_sitemap_urls --

def test_filter_sitemap_urls_keeps_only_real_matching_paths():
    """Validation criterion -- invalid/unwanted URLs are filtered out
    via a real, simple glob pattern against the URL's own path."""
    urls = parse_sitemap(_REAL_URLSET)
    assert filter_sitemap_urls(urls, ["/blog/*"]) == [
        "https://example.com/blog/post-1",
        "https://example.com/blog/post-2",
    ]


def test_filter_sitemap_urls_with_no_patterns_keeps_everything():
    urls = parse_sitemap(_REAL_URLSET)
    assert filter_sitemap_urls(urls, None) == urls
    assert filter_sitemap_urls(urls, []) == urls


def test_filter_sitemap_urls_supports_multiple_patterns():
    urls = parse_sitemap(_REAL_URLSET)
    assert filter_sitemap_urls(urls, ["/blog/*", "/about"]) == urls


# -------------------------------------------------------- fetch_sitemap --

async def test_fetch_sitemap_transparently_decompresses_real_gzip_content():
    """Real protocol detail, verified before writing this module: real
    sitemaps are commonly gzip-compressed -- the real network fetch
    itself is mocked here (already covered for real elsewhere), but the
    real gzip round-trip and detection logic is exercised for real."""
    compressed = gzip.compress(_REAL_URLSET)
    with patch("api.services.sitemap_extraction.fetch_url_content", new=AsyncMock(return_value=(compressed, "https://example.com/sitemap.xml.gz"))):
        content = await fetch_sitemap("https://example.com/sitemap.xml.gz")
    assert content == _REAL_URLSET
    assert parse_sitemap(content) == [
        "https://example.com/blog/post-1", "https://example.com/blog/post-2", "https://example.com/about",
    ]


async def test_fetch_sitemap_passes_through_real_uncompressed_content_unchanged():
    with patch("api.services.sitemap_extraction.fetch_url_content", new=AsyncMock(return_value=(_REAL_URLSET, "https://example.com/sitemap.xml"))):
        content = await fetch_sitemap("https://example.com/sitemap.xml")
    assert content == _REAL_URLSET


async def test_fetch_sitemap_raises_a_clear_error_for_content_that_only_looks_gzipped():
    """Real finding: content whose first two bytes happen to match
    gzip's own magic number but isn't valid gzip data raises a real
    gzip.BadGzipFile (an OSError, not a ValueError) -- confirmed for
    real, and re-raised here as the SAME ValueError every other real
    failure in this module uses."""
    fake_gzip_looking_bytes = b"\x1f\x8bnot really gzip data after the magic bytes"
    with patch("api.services.sitemap_extraction.fetch_url_content", new=AsyncMock(return_value=(fake_gzip_looking_bytes, "https://example.com/sitemap.xml.gz"))):
        with pytest.raises(ValueError):
            await fetch_sitemap("https://example.com/sitemap.xml.gz")
