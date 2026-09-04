"""Partie 5.2.6 -- URL reader tool. Mocks at the level of the REAL,
already-tested SSRF-safe functions this module reuses
(`api.services.url_fetching.fetch_url_content`/`validate_url`) rather
than re-testing SSRF protection itself (covered by
tests/test_url_fetching.py) -- this file verifies real reuse and real
tool-specific behavior (size cap, domain allowlist, metadata)."""

import pytest

from api.config import settings
from api.tools.url_reader import (
    URL_READER_TOOL, UrlReaderError, extract_url_content, read_url, read_url_with_metadata,
)

_REAL_HTML = "<html><head><title>Real Page</title></head><body><article><p>Real main content here.</p></article></body></html>"


def _patch_fetch(monkeypatch, content: bytes = _REAL_HTML.encode(), final_url: str = "https://example.com/page"):
    async def _fake_fetch(url):
        return content, final_url

    monkeypatch.setattr("api.tools.url_reader.validate_url", lambda url: url)
    monkeypatch.setattr("api.tools.url_reader.fetch_url_content", _fake_fetch)


# --------------------------------------- read_url --


async def test_read_url_extracts_real_main_content(monkeypatch):
    """Validation criterion: la lecture d'URL fonctionne."""
    _patch_fetch(monkeypatch)
    content = await read_url("https://example.com/page")
    assert "Real main content here." in content


async def test_read_url_with_metadata_includes_real_title_and_source(monkeypatch):
    """Validation criterion: les métadonnées sont extraites."""
    _patch_fetch(monkeypatch)
    result = await read_url_with_metadata("https://example.com/page")
    assert result["title"] == "Real Page"
    assert result["source_url"] == "https://example.com/page"
    assert "content" in result


# --------------------------------------- validation / robustness --


async def test_read_url_rejects_a_real_invalid_url(monkeypatch):
    """Validation criterion: les URLs invalides sont rejetées."""
    def _raise(url):
        raise ValueError("URL scheme must be http/https")

    monkeypatch.setattr("api.tools.url_reader.validate_url", _raise)
    with pytest.raises(ValueError):
        await read_url("ftp://example.com")


async def test_read_url_wraps_a_real_fetch_failure(monkeypatch):
    """Validation criterion: robustesse -- que se passe-t-il si l'URL
    est inaccessible."""
    async def _fail(url):
        raise ValueError("URL is not accessible: connection refused")

    monkeypatch.setattr("api.tools.url_reader.validate_url", lambda url: url)
    monkeypatch.setattr("api.tools.url_reader.fetch_url_content", _fail)
    with pytest.raises(UrlReaderError, match="not accessible"):
        await read_url("https://unreachable.example.com")


async def test_read_url_enforces_the_real_size_cap(monkeypatch):
    monkeypatch.setattr(settings, "URL_READER_MAX_SIZE", 10)
    _patch_fetch(monkeypatch, content=b"x" * 100)
    with pytest.raises(UrlReaderError, match="exceeds"):
        await read_url("https://example.com/big")


# --------------------------------------- domain allowlist/blocklist --


async def test_read_url_rejects_a_real_blocked_domain(monkeypatch):
    monkeypatch.setattr(settings, "URL_READER_BLOCKED_DOMAINS", ["blocked.com"])
    _patch_fetch(monkeypatch, final_url="https://blocked.com/page")
    with pytest.raises(UrlReaderError, match="blocked"):
        await read_url("https://blocked.com/page")


async def test_read_url_rejects_a_domain_outside_the_real_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "URL_READER_ALLOWED_DOMAINS", ["allowed.com"])
    monkeypatch.setattr("api.tools.url_reader.validate_url", lambda url: url)
    with pytest.raises(UrlReaderError, match="allowlist"):
        await read_url("https://not-allowed.com/page")


# --------------------------------------- extract_url_content --


def test_extract_url_content_uses_real_readability_extraction():
    content = extract_url_content("https://example.com", _REAL_HTML)
    assert "Real main content here." in content


# --------------------------------------- tool wiring --


async def test_url_reader_tool_handler_returns_real_content(monkeypatch):
    _patch_fetch(monkeypatch)
    result = await URL_READER_TOOL.handler(url="https://example.com/page")
    assert "Real main content here." in result


async def test_url_reader_tool_handler_returns_a_real_error_message(monkeypatch):
    async def _fail(url):
        raise ValueError("timeout")

    monkeypatch.setattr("api.tools.url_reader.validate_url", lambda url: url)
    monkeypatch.setattr("api.tools.url_reader.fetch_url_content", _fail)
    result = await URL_READER_TOOL.handler(url="https://example.com/page")
    assert "Could not read URL" in result
