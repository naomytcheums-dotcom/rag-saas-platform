"""
Partie 2.1.14 -- fast-tier tests for api/services/google_drive_extraction.py.
No real network call: every real HTTP interaction is exercised through
`httpx.MockTransport` (a REAL httpx testing utility -- request/response
parsing, headers, status codes, and JSON encoding/decoding all run for
real; only the actual network transport is swapped for a fake one that
resolves instantly and deterministically). Same "real library behavior,
fake network" split as tests/test_github_extraction.py's own module
docstring.

Unlike Partie 2.1.12/2.1.13's own fast-tier tests, whose real
error-mapping tests were WRITTEN after independently confirming the
real, live shape of each error against the real GitHub API, this
module's real, live-confirmed shapes (see api/services/google_drive_extraction.py's
own module docstring for exactly which ones, and how) are baked into
the mock responses below -- no valid Google OAuth credentials were
available to test the SUCCESS path against a real account (see that
same docstring for why), but the FAILURE shapes these tests assert
against are real, not invented.
"""

import time

import httpx
import pytest

from api.config import settings
from api.services.google_drive_extraction import (
    GOOGLE_DRIVE_FOLDER_MIME_TYPE,
    GoogleDriveAuthError,
    GoogleDriveRateLimitError,
    _access_token_cache,
    authenticate_drive,
    download_drive_file,
    extract_drive_metadata,
    get_drive_file,
    list_drive_files,
    should_include_drive_file,
)


@pytest.fixture(autouse=True)
def _clear_token_cache():
    """The module-level access-token cache is real, shared, per-process
    state (see that module's own docstring) -- cleared before/after
    every test here so one test's cached token never leaks into
    another's assertions."""
    _access_token_cache.clear()
    yield
    _access_token_cache.clear()


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr("api.services.google_drive_extraction._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def _drive_error(status_code: int, message: str, error_status: str) -> httpx.Response:
    """Google's own real, NESTED error envelope shape, confirmed live
    before writing this module -- see that module's own docstring."""
    return httpx.Response(status_code, json={"error": {"code": status_code, "message": message, "status": error_status}})


# ------------------------------------------------------------ authenticate_drive --

async def test_authenticate_drive_exchanges_the_refresh_token_for_a_real_access_token(monkeypatch):
    def handler(request):
        assert request.url.path == "/token"
        return httpx.Response(200, json={"access_token": "real-looking-access-token", "expires_in": 3600, "token_type": "Bearer"})

    _patch_client(monkeypatch, handler)
    token = await authenticate_drive("a-refresh-token")
    assert token == "real-looking-access-token"


async def test_authenticate_drive_caches_and_does_not_refetch_before_expiry(monkeypatch):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"access_token": f"token-{len(calls)}", "expires_in": 3600})

    _patch_client(monkeypatch, handler)
    first = await authenticate_drive("a-refresh-token")
    second = await authenticate_drive("a-refresh-token")
    assert first == second
    assert len(calls) == 1


async def test_authenticate_drive_refreshes_again_within_the_real_safety_margin(monkeypatch):
    """Validation criterion / vision critique Q4: a token nearing its
    real expiry is proactively refreshed, not used until a real 401
    actually happens."""
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"access_token": f"token-{len(calls)}", "expires_in": 3600})

    _patch_client(monkeypatch, handler)
    first = await authenticate_drive("a-refresh-token")
    cached_token, _expires_at = _access_token_cache["a-refresh-token"]
    _access_token_cache["a-refresh-token"] = (cached_token, time.time() + 30)  # inside the real 60s margin

    second = await authenticate_drive("a-refresh-token")
    assert second != first
    assert len(calls) == 2


async def test_authenticate_drive_raises_a_clear_error_for_a_real_invalid_client(monkeypatch):
    """Validation criterion: un token invalide est rejeté -- this
    module's own docstring confirms this exact real, live response
    shape against the real Google OAuth endpoint."""
    _patch_client(monkeypatch, lambda request: httpx.Response(401, json={"error": "invalid_client", "error_description": "The OAuth client was not found."}))
    with pytest.raises(GoogleDriveAuthError, match="invalid_client"):
        await authenticate_drive("any-refresh-token")


async def test_authenticate_drive_raises_a_clear_error_for_a_real_invalid_grant(monkeypatch):
    """A real, expired/revoked refresh token against a real, valid
    client -- Google's own documented `invalid_grant` (see that
    module's own docstring for why this specific shape is asserted on
    documentation rather than a live trigger)."""
    _patch_client(monkeypatch, lambda request: httpx.Response(400, json={"error": "invalid_grant", "error_description": "Token has been expired or revoked."}))
    with pytest.raises(GoogleDriveAuthError, match="invalid_grant"):
        await authenticate_drive("an-expired-refresh-token")


# --------------------------------------------------------- _raise_for_drive_response --

async def test_get_drive_file_raises_for_a_real_401_unauthenticated(monkeypatch):
    _patch_client(monkeypatch, lambda request: _drive_error(401, "Request had invalid authentication credentials.", "UNAUTHENTICATED"))
    with pytest.raises(GoogleDriveAuthError, match="rejected the configured credentials"):
        await get_drive_file("some-file-id", "a-bad-access-token")


async def test_get_drive_file_raises_for_a_real_403_permission_denied(monkeypatch):
    """Validation criterion: confirmed for real that NO Authorization
    header at all gets this exact real 403/PERMISSION_DENIED shape."""
    _patch_client(monkeypatch, lambda request: _drive_error(403, "Method doesn't allow unregistered callers.", "PERMISSION_DENIED"))
    with pytest.raises(GoogleDriveAuthError):
        await get_drive_file("some-file-id", "")


async def test_get_drive_file_raises_a_distinguishable_rate_limit_error(monkeypatch):
    _patch_client(monkeypatch, lambda request: _drive_error(403, "User Rate Limit Exceeded", "USER_RATE_LIMIT_EXCEEDED"))
    with pytest.raises(GoogleDriveRateLimitError):
        await get_drive_file("some-file-id", "a-token")


async def test_get_drive_file_raises_for_a_real_404(monkeypatch):
    _patch_client(monkeypatch, lambda request: _drive_error(404, "File not found: nope.", ""))
    with pytest.raises(ValueError, match="was not found"):
        await get_drive_file("nope", "a-token")


async def test_get_drive_file_returns_real_metadata_on_success(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(200, json={"id": "f1", "name": "report.pdf", "mimeType": "application/pdf", "size": "1234"}))
    data = await get_drive_file("f1", "a-token")
    assert data["name"] == "report.pdf"


# ------------------------------------------------------------- list_drive_files --

async def test_list_drive_files_lists_and_filters_a_real_folders_children(monkeypatch):
    """Validation criterion: l'import d'un dossier fonctionne, les
    fichiers sont filtrés par extension -- a real subfolder and a real
    native Google Doc are excluded regardless of patterns."""
    def handler(request):
        assert "'folder-1' in parents" in request.url.params["q"]
        return httpx.Response(200, json={"files": [
            {"id": "f1", "name": "report.pdf", "mimeType": "application/pdf", "size": "100"},
            {"id": "f2", "name": "subfolder", "mimeType": GOOGLE_DRIVE_FOLDER_MIME_TYPE},
            {"id": "f3", "name": "My Doc", "mimeType": "application/vnd.google-apps.document"},
            {"id": "f4", "name": "notes.txt", "mimeType": "text/plain", "size": "50"},
        ]})

    _patch_client(monkeypatch, handler)
    files = await list_drive_files("folder-1", "a-token")
    assert [f["id"] for f in files] == ["f1", "f4"]


async def test_list_drive_files_paginates_through_real_next_page_tokens(monkeypatch):
    pages = {
        None: {"files": [{"id": "f1", "name": "a.pdf", "mimeType": "application/pdf"}], "nextPageToken": "page2"},
        "page2": {"files": [{"id": "f2", "name": "b.pdf", "mimeType": "application/pdf"}]},
    }

    def handler(request):
        token = request.url.params.get("pageToken")
        return httpx.Response(200, json=pages[token])

    _patch_client(monkeypatch, handler)
    files = await list_drive_files("folder-1", "a-token")
    assert [f["id"] for f in files] == ["f1", "f2"]


async def test_list_drive_files_applies_real_include_patterns(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(200, json={"files": [
        {"id": "f1", "name": "report.pdf", "mimeType": "application/pdf"},
        {"id": "f2", "name": "image.png", "mimeType": "image/png"},
    ]}))
    files = await list_drive_files("folder-1", "a-token", patterns=[".pdf"])
    assert [f["id"] for f in files] == ["f1"]


# --------------------------------------------------------- download_drive_file --

async def test_download_drive_file_returns_real_binary_content(monkeypatch):
    def handler(request):
        assert request.url.params["alt"] == "media"
        return httpx.Response(200, content=b"%PDF-1.4 fake but real-looking pdf bytes")

    _patch_client(monkeypatch, handler)
    content = await download_drive_file("f1", "a-token")
    assert content.startswith(b"%PDF-1.4")


async def test_download_drive_file_raises_for_a_real_auth_failure(monkeypatch):
    _patch_client(monkeypatch, lambda request: _drive_error(401, "Invalid Credentials", "UNAUTHENTICATED"))
    with pytest.raises(GoogleDriveAuthError):
        await download_drive_file("f1", "a-bad-token")


# ------------------------------------------------------------- extract_drive_metadata --

def test_extract_drive_metadata_reports_name_type_size_and_dates():
    """Validation criterion: extraire les métadonnées (nom, type,
    taille, date)."""
    file = {
        "id": "f1", "name": "report.pdf", "mimeType": "application/pdf", "size": "104857600",
        "createdTime": "2026-01-01T00:00:00.000Z", "modifiedTime": "2026-01-02T00:00:00.000Z",
        "webViewLink": "https://drive.google.com/file/d/f1/view",
    }
    metadata = extract_drive_metadata(file)
    assert metadata == {
        "id": "f1", "name": "report.pdf", "mime_type": "application/pdf", "size": 104857600,
        "created_at": "2026-01-01T00:00:00.000Z", "modified_at": "2026-01-02T00:00:00.000Z",
        "web_view_link": "https://drive.google.com/file/d/f1/view",
    }


def test_extract_drive_metadata_handles_a_real_native_google_doc_with_no_size():
    """Real Drive API detail: a native Google Workspace file genuinely
    has no `size` field at all (no downloadable binary to measure)."""
    metadata = extract_drive_metadata({"id": "d1", "name": "My Doc", "mimeType": "application/vnd.google-apps.document"})
    assert metadata["size"] is None


def test_extract_drive_metadata_converts_the_real_string_size_to_a_real_int():
    """Real Drive API detail: `size` is a real JSON STRING, not a
    number (Google's own int64-precision-safety convention)."""
    metadata = extract_drive_metadata({"id": "f1", "name": "big.pdf", "mimeType": "application/pdf", "size": "9999999999"})
    assert metadata["size"] == 9999999999
    assert isinstance(metadata["size"], int)


# ---------------------------------------------------------- should_include_drive_file --

def test_should_include_drive_file_excludes_real_folders():
    assert should_include_drive_file({"mimeType": GOOGLE_DRIVE_FOLDER_MIME_TYPE}, None) is False


def test_should_include_drive_file_excludes_real_native_google_workspace_files():
    """Validation criterion / this module's own docstring: a real
    native Google Doc/Sheet/Slide is excluded regardless of patterns
    -- Partie 2.1.15's own separate scope, not re-implemented here."""
    for mime_type in ("application/vnd.google-apps.document", "application/vnd.google-apps.spreadsheet", "application/vnd.google-apps.presentation"):
        assert should_include_drive_file({"mimeType": mime_type}, None) is False


def test_should_include_drive_file_matches_by_real_extension():
    patterns = settings.google_drive_include_patterns_list
    assert should_include_drive_file({"name": "report.pdf", "mimeType": "application/pdf"}, patterns) is True
    assert should_include_drive_file({"name": "photo.png", "mimeType": "image/png"}, patterns) is False


def test_should_include_drive_file_enforces_the_real_size_cap(monkeypatch):
    """Validation criterion / vision critique Q4: un fichier trop gros
    est rejeté."""
    monkeypatch.setattr(settings, "GOOGLE_DRIVE_MAX_FILE_SIZE", 1000)
    small = {"name": "a.pdf", "mimeType": "application/pdf", "size": "500"}
    big = {"name": "b.pdf", "mimeType": "application/pdf", "size": "5000"}
    assert should_include_drive_file(small, None) is True
    assert should_include_drive_file(big, None) is False


def test_should_include_drive_file_with_no_size_field_is_not_rejected_on_size_alone():
    """A real file that genuinely reports no size (rare, but real APIs
    can omit it) must not be excluded by the size check alone."""
    assert should_include_drive_file({"name": "a.pdf", "mimeType": "application/pdf"}, None) is True
