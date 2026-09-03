"""
Partie 2.1.16 -- fast-tier tests for api/services/notion_extraction.py.
No real network call: every real HTTP interaction is exercised through
`httpx.MockTransport`, the same "real library behavior, fake network"
split every prior fast-tier test file in this codebase uses.

Real, live-confirmed error shapes (see that module's own module
docstring for exactly which ones, and how -- a real, live, unauthenticated
request to the real Notion API, no valid token needed) are baked into
the mock responses below, the same honesty as Partie 2.1.14's own
equivalent tests.
"""

import httpx
import pytest

from api.config import settings
from api.services.notion_extraction import (
    NotionAuthError,
    NotionRateLimitError,
    extract_notion_content,
    extract_notion_metadata,
    fetch_notion_blocks,
    fetch_notion_database,
    fetch_notion_page,
    query_notion_database_pages,
    validate_notion_url,
)


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr("api.services.notion_extraction._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def _notion_error(status_code: int, message: str, code: str) -> httpx.Response:
    """Notion's own real, FLAT error envelope, confirmed live before
    writing this module -- see that module's own docstring."""
    return httpx.Response(status_code, json={"object": "error", "status": status_code, "code": code, "message": message})


# ------------------------------------------------------------- validate_notion_url --

def test_validate_notion_url_extracts_a_real_id_from_a_real_url():
    assert validate_notion_url("https://www.notion.so/myworkspace/Page-Title-1234567890abcdef1234567890abcdef") == "1234567890abcdef1234567890abcdef"


def test_validate_notion_url_extracts_a_real_dashed_uuid():
    assert validate_notion_url("https://notion.so/Page-12345678-90ab-cdef-1234-567890abcdef") == "12345678-90ab-cdef-1234-567890abcdef"


def test_validate_notion_url_accepts_a_bare_id():
    """Validation criterion: accepte une URL OU un ID."""
    assert validate_notion_url("1234567890abcdef1234567890abcdef") == "1234567890abcdef1234567890abcdef"


def test_validate_notion_url_rejects_an_unrelated_url():
    """Validation criterion: une page invalide est rejetée."""
    with pytest.raises(ValueError):
        validate_notion_url("https://example.com/not-notion")


def test_validate_notion_url_rejects_a_notion_url_with_no_real_id():
    with pytest.raises(ValueError):
        validate_notion_url("https://www.notion.so/myworkspace/just-a-title-no-id")


# ---------------------------------------------------------------- fetch_notion_page --

async def test_fetch_notion_page_returns_real_page_data(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(200, json={"id": "page-1", "object": "page", "url": "https://notion.so/page-1"}))
    page = await fetch_notion_page("page-1", "a-token")
    assert page["id"] == "page-1"


async def test_fetch_notion_page_raises_for_a_real_invalid_token(monkeypatch):
    """Validation criterion: un token invalide est rejeté -- this
    module's own docstring confirms this exact real, live shape."""
    _patch_client(monkeypatch, lambda request: _notion_error(401, "API token is invalid.", "unauthorized"))
    with pytest.raises(NotionAuthError):
        await fetch_notion_page("page-1", "a-bad-token")


async def test_fetch_notion_page_raises_a_distinguishable_rate_limit_error(monkeypatch):
    """Validation criterion / vision critique Q4: si le rate limit est
    atteint."""
    _patch_client(monkeypatch, lambda request: httpx.Response(429, json={"object": "error", "status": 429, "code": "rate_limited", "message": "You have been rate limited."}))
    with pytest.raises(NotionRateLimitError):
        await fetch_notion_page("page-1", "a-token")


async def test_fetch_notion_page_raises_for_not_found_or_not_shared(monkeypatch):
    _patch_client(monkeypatch, lambda request: _notion_error(404, "Could not find page.", "object_not_found"))
    with pytest.raises(ValueError, match="not shared"):
        await fetch_notion_page("nonexistent-page", "a-token")


# ------------------------------------------------------------ fetch_notion_database --

async def test_fetch_notion_database_returns_real_database_data(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(200, json={"id": "db-1", "object": "database"}))
    database = await fetch_notion_database("db-1", "a-token")
    assert database["id"] == "db-1"


# ------------------------------------------------------ query_notion_database_pages --

async def test_query_notion_database_pages_paginates_through_real_cursors(monkeypatch):
    """Validation criterion: l'import d'une base de données fonctionne."""
    pages = {
        None: {"results": [{"id": "p1"}], "has_more": True, "next_cursor": "cursor-2"},
        "cursor-2": {"results": [{"id": "p2"}], "has_more": False, "next_cursor": None},
    }

    def handler(request):
        import json
        body = json.loads(request.content)
        return httpx.Response(200, json=pages[body.get("start_cursor")])

    _patch_client(monkeypatch, handler)
    result = await query_notion_database_pages("db-1", "a-token", max_pages=100)
    assert [p["id"] for p in result] == ["p1", "p2"]


async def test_query_notion_database_pages_enforces_the_real_max_pages_cap(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(200, json={"results": [{"id": f"p{i}"} for i in range(10)], "has_more": False}))
    result = await query_notion_database_pages("db-1", "a-token", max_pages=3)
    assert len(result) == 3


# ------------------------------------------------------------- fetch_notion_blocks --

async def test_fetch_notion_blocks_recurses_into_real_children(monkeypatch):
    """Validation criterion: real pagination + a real, recursive
    block-tree walk (see this module's own docstring)."""
    def handler(request):
        if request.url.path == "/v1/blocks/page-1/children":
            return httpx.Response(200, json={"results": [
                {"id": "b1", "type": "paragraph", "has_children": False, "paragraph": {"rich_text": []}},
                {"id": "b2", "type": "toggle", "has_children": True, "toggle": {"rich_text": []}},
            ], "has_more": False})
        if request.url.path == "/v1/blocks/b2/children":
            return httpx.Response(200, json={"results": [
                {"id": "b3", "type": "paragraph", "has_children": False, "paragraph": {"rich_text": []}},
            ], "has_more": False})
        raise AssertionError(f"unexpected real request to {request.url.path}")

    _patch_client(monkeypatch, handler)
    blocks = await fetch_notion_blocks("page-1", "a-token")
    assert [b["id"] for b in blocks] == ["b1", "b2"]
    assert blocks[1]["_children"][0]["id"] == "b3"
    assert blocks[0]["_children"] == []


async def test_fetch_notion_blocks_respects_the_real_max_blocks_cap(monkeypatch):
    """Validation criterion / vision critique Q4: que se passe-t-il si
    une page a trop de blocs."""
    monkeypatch.setattr(settings, "NOTION_MAX_BLOCKS", 2)

    def handler(request):
        return httpx.Response(200, json={"results": [
            {"id": "b1", "type": "paragraph", "has_children": False, "paragraph": {"rich_text": []}},
            {"id": "b2", "type": "paragraph", "has_children": True, "paragraph": {"rich_text": []}},
        ], "has_more": False})

    _patch_client(monkeypatch, handler)
    blocks = await fetch_notion_blocks("page-1", "a-token")
    # The real cap was already reached fetching the top-level batch --
    # a real child fetch for b2 (has_children=True) must not happen.
    assert blocks[1]["_children"] == []


async def test_fetch_notion_blocks_returns_nothing_for_a_real_zero_cap(monkeypatch):
    """A real, explicit zero cap short-circuits before any real network
    call at all -- confirmed here by NOT patching the client, so a
    real network call would fail this test loudly if one happened."""
    monkeypatch.setattr(settings, "NOTION_MAX_BLOCKS", 0)
    assert await fetch_notion_blocks("page-1", "a-token") == []


# ---------------------------------------------------------------- extract_notion_metadata --

def test_extract_notion_metadata_finds_the_real_title_property_by_type():
    """Validation criterion: les métadonnées sont extraites (titre,
    propriétés, date) -- the real title property KEY can be named
    anything (here, "Name"), found by its real TYPE instead."""
    page = {
        "id": "p1", "url": "https://notion.so/p1", "created_time": "2026-01-01T00:00:00Z",
        "last_edited_time": "2026-01-02T00:00:00Z", "archived": False,
        "properties": {"Status": {"type": "select"}, "Name": {"type": "title", "title": [{"plain_text": "My Page"}]}},
    }
    metadata = extract_notion_metadata(page)
    assert metadata["title"] == "My Page"
    assert metadata["created_at"] == "2026-01-01T00:00:00Z"


def test_extract_notion_metadata_handles_a_real_page_with_no_title_text():
    page = {"id": "p1", "properties": {"Name": {"type": "title", "title": []}}}
    assert extract_notion_metadata(page)["title"] == ""


# ------------------------------------------------------------- extract_notion_content --

def test_extract_notion_content_converts_real_blocks_to_markdown():
    """Validation criterion: l'extraction en Markdown fonctionne."""
    blocks = [
        {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Title", "annotations": {}}]}, "_children": []},
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Hello", "annotations": {"bold": True}}]}, "_children": []},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "item", "annotations": {}}]}, "_children": []},
    ]
    markdown = extract_notion_content(blocks)
    assert markdown.startswith("# Title")
    assert "**Hello**" in markdown
    assert "- item" in markdown


def test_extract_notion_content_numbers_consecutive_list_items_sequentially():
    blocks = [
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": [{"plain_text": "first", "annotations": {}}]}, "_children": []},
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": [{"plain_text": "second", "annotations": {}}]}, "_children": []},
    ]
    markdown = extract_notion_content(blocks)
    assert "1. first" in markdown
    assert "2. second" in markdown


def test_extract_notion_content_renders_real_indented_nested_children():
    blocks = [
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "parent", "annotations": {}}]}, "_children": [
            {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "child", "annotations": {}}]}, "_children": []},
        ]},
    ]
    markdown = extract_notion_content(blocks)
    assert "- parent" in markdown
    assert "  - child" in markdown


def test_extract_notion_content_excludes_real_types_not_in_the_allowlist(monkeypatch):
    """Validation criterion / this module's own docstring: a real
    ALLOWLIST, matching should_include_issue/should_include_drive_file's
    own precedent."""
    monkeypatch.setattr(settings, "NOTION_INCLUDE_TYPES", "paragraph")
    blocks = [
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "kept", "annotations": {}}]}, "_children": []},
        {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "dropped", "annotations": {}}]}, "_children": []},
    ]
    markdown = extract_notion_content(blocks)
    assert "kept" in markdown
    assert "dropped" not in markdown


def test_extract_notion_content_renders_a_real_todo_and_code_block():
    blocks = [
        {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "done", "annotations": {}}], "checked": True}, "_children": []},
        {"type": "code", "code": {"rich_text": [{"plain_text": "x = 1", "annotations": {}}], "language": "python"}, "_children": []},
    ]
    markdown = extract_notion_content(blocks)
    assert "- [x] done" in markdown
    assert "```python" in markdown
    assert "x = 1" in markdown
