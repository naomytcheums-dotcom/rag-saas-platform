"""
Partie 2.1.18 -- fast-tier tests for api/services/onedrive_extraction.py.
No real network call: every real HTTP interaction is exercised through
`httpx.MockTransport`, the same "real library behavior, fake network"
split as tests/test_google_drive_extraction.py's own module docstring.

Same honesty as that module: no valid Microsoft/Azure credentials were
available to test the SUCCESS path against a real account, but the
FAILURE shapes these tests assert against are the real, live-confirmed
ones documented in api/services/onedrive_extraction.py's own module
docstring, not invented.
"""

import time

import httpx
import pytest

from api.config import settings
from api.services.onedrive_extraction import (
    OneDriveAuthError,
    OneDriveRateLimitError,
    _access_token_cache,
    authenticate_onedrive,
    download_onedrive_file,
    extract_onedrive_metadata,
    get_onedrive_file,
    list_onedrive_files,
    should_include_onedrive_file,
)


@pytest.fixture(autouse=True)
def _clear_token_cache():
    """Same real, shared, per-process module-level cache reasoning as
    tests/test_google_drive_extraction.py's own equivalent fixture."""
    _access_token_cache.clear()
    yield
    _access_token_cache.clear()


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr("api.services.onedrive_extraction._client", lambda *args, **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def _graph_error(status_code: int, message: str, code: str) -> httpx.Response:
    """Microsoft Graph's own real, NESTED error envelope shape,
    confirmed live before writing this module -- see that module's own
    docstring."""
    return httpx.Response(status_code, json={"error": {"code": code, "message": message, "innerError": {}}})


# ---------------------------------------------------------- authenticate_onedrive --

async def test_authenticate_onedrive_exchanges_the_refresh_token_for_a_real_access_token(monkeypatch):
    def handler(request):
        assert request.url.path.endswith("/token")
        return httpx.Response(200, json={"access_token": "real-looking-access-token", "expires_in": 3600, "token_type": "Bearer"})

    _patch_client(monkeypatch, handler)
    token = await authenticate_onedrive("a-refresh-token")
    assert token == "real-looking-access-token"


async def test_authenticate_onedrive_caches_and_does_not_refetch_before_expiry(monkeypatch):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"access_token": f"token-{len(calls)}", "expires_in": 3600})

    _patch_client(monkeypatch, handler)
    first = await authenticate_onedrive("a-refresh-token")
    second = await authenticate_onedrive("a-refresh-token")
    assert first == second
    assert len(calls) == 1


async def test_authenticate_onedrive_refreshes_again_within_the_real_safety_margin(monkeypatch):
    """Validation criterion / vision critique Q4: a token nearing its
    real expiry is proactively refreshed, not used until a real 401
    actually happens."""
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"access_token": f"token-{len(calls)}", "expires_in": 3600})

    _patch_client(monkeypatch, handler)
    first = await authenticate_onedrive("a-refresh-token")
    cached_token, _expires_at = _access_token_cache["a-refresh-token"]
    _access_token_cache["a-refresh-token"] = (cached_token, time.time() + 30)  # inside the real 60s margin

    second = await authenticate_onedrive("a-refresh-token")
    assert second != first
    assert len(calls) == 2


async def test_authenticate_onedrive_raises_a_clear_error_for_a_real_missing_client_id(monkeypatch):
    """Validation criterion: un token invalide est rejeté -- this
    module's own docstring confirms this exact real, live response
    shape against the real Microsoft identity platform."""
    _patch_client(monkeypatch, lambda request: httpx.Response(400, json={
        "error": "invalid_request",
        "error_description": "AADSTS900144: The request body must contain the following parameter: 'client_id'.",
    }))
    with pytest.raises(OneDriveAuthError, match="invalid_request"):
        await authenticate_onedrive("any-refresh-token")


async def test_authenticate_onedrive_raises_a_clear_error_for_a_real_invalid_grant(monkeypatch):
    """A real, malformed/expired/revoked refresh token -- Microsoft's
    own documented `invalid_grant` (see that module's own docstring for
    the real, live AADSTS9002313 response this mirrors, and why
    Microsoft's own shape genuinely differs from Google's)."""
    _patch_client(monkeypatch, lambda request: httpx.Response(400, json={
        "error": "invalid_grant",
        "error_description": "AADSTS9002313: Invalid request. Request is malformed or invalid.",
    }))
    with pytest.raises(OneDriveAuthError, match="invalid_grant"):
        await authenticate_onedrive("a-malformed-refresh-token")


# --------------------------------------------------------- _raise_for_graph_response --

async def test_get_onedrive_file_raises_for_a_real_401_invalid_authentication_token(monkeypatch):
    """Validation criterion: confirmed for real that NO Authorization
    header at all gets this exact real 401/InvalidAuthenticationToken
    shape from the live Graph API."""
    _patch_client(monkeypatch, lambda request: _graph_error(401, "Access token is empty.", "InvalidAuthenticationToken"))
    with pytest.raises(OneDriveAuthError, match="rejected the configured credentials"):
        await get_onedrive_file("some-item-id", "")


async def test_get_onedrive_file_raises_a_distinguishable_rate_limit_error(monkeypatch):
    _patch_client(monkeypatch, lambda request: _graph_error(429, "Too many requests.", "activityLimitReached"))
    with pytest.raises(OneDriveRateLimitError):
        await get_onedrive_file("some-item-id", "a-token")


async def test_get_onedrive_file_raises_for_a_real_404(monkeypatch):
    _patch_client(monkeypatch, lambda request: _graph_error(404, "The resource could not be found.", "itemNotFound"))
    with pytest.raises(ValueError, match="was not found"):
        await get_onedrive_file("nope", "a-token")


async def test_get_onedrive_file_returns_real_metadata_on_success(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(200, json={"id": "f1", "name": "report.pdf", "size": 1234, "file": {"mimeType": "application/pdf"}}))
    data = await get_onedrive_file("f1", "a-token")
    assert data["name"] == "report.pdf"


# ------------------------------------------------------------ list_onedrive_files --

async def test_list_onedrive_files_lists_and_filters_a_real_folders_children(monkeypatch):
    """Validation criterion: l'import d'un dossier fonctionne, les
    fichiers sont filtrés par extension -- a real subfolder is excluded
    regardless of patterns."""
    def handler(request):
        assert "/items/folder-1/children" in str(request.url)
        return httpx.Response(200, json={"value": [
            {"id": "f1", "name": "report.pdf", "size": 100, "file": {"mimeType": "application/pdf"}},
            {"id": "f2", "name": "subfolder", "folder": {"childCount": 3}},
            {"id": "f3", "name": "notes.txt", "size": 50, "file": {"mimeType": "text/plain"}},
        ]})

    _patch_client(monkeypatch, handler)
    files = await list_onedrive_files("folder-1", "a-token")
    assert [f["id"] for f in files] == ["f1", "f3"]


async def test_list_onedrive_files_paginates_through_real_odata_next_links(monkeypatch):
    """Real Graph API detail: `@odata.nextLink` is already a full,
    ready-to-call URL, unlike Drive's own opaque `nextPageToken`."""
    def handler(request):
        if "page2" in str(request.url):
            return httpx.Response(200, json={"value": [{"id": "f2", "name": "b.pdf", "size": 10, "file": {"mimeType": "application/pdf"}}]})
        return httpx.Response(200, json={
            "value": [{"id": "f1", "name": "a.pdf", "size": 10, "file": {"mimeType": "application/pdf"}}],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/drive/items/folder-1/children?page2",
        })

    _patch_client(monkeypatch, handler)
    files = await list_onedrive_files("folder-1", "a-token")
    assert [f["id"] for f in files] == ["f1", "f2"]


async def test_list_onedrive_files_applies_real_include_patterns(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(200, json={"value": [
        {"id": "f1", "name": "report.pdf", "size": 10, "file": {"mimeType": "application/pdf"}},
        {"id": "f2", "name": "image.png", "size": 10, "file": {"mimeType": "image/png"}},
    ]}))
    files = await list_onedrive_files("folder-1", "a-token", patterns=[".pdf"])
    assert [f["id"] for f in files] == ["f1"]


# --------------------------------------------------------- download_onedrive_file --

async def test_download_onedrive_file_returns_real_binary_content(monkeypatch):
    def handler(request):
        assert "/content" in str(request.url)
        return httpx.Response(200, content=b"%PDF-1.4 fake but real-looking pdf bytes")

    _patch_client(monkeypatch, handler)
    content = await download_onedrive_file("f1", "a-token")
    assert content.startswith(b"%PDF-1.4")


async def test_download_onedrive_file_raises_for_a_real_auth_failure(monkeypatch):
    _patch_client(monkeypatch, lambda request: _graph_error(401, "Access token is empty.", "InvalidAuthenticationToken"))
    with pytest.raises(OneDriveAuthError):
        await download_onedrive_file("f1", "a-bad-token")


# ---------------------------------------------------------- extract_onedrive_metadata --

def test_extract_onedrive_metadata_reports_name_type_size_and_dates():
    """Validation criterion: extraire les métadonnées (nom, type,
    taille, date)."""
    file = {
        "id": "f1", "name": "report.pdf", "size": 104857600,
        "createdDateTime": "2026-01-01T00:00:00Z", "lastModifiedDateTime": "2026-01-02T00:00:00Z",
        "webUrl": "https://onedrive.live.com/f1", "file": {"mimeType": "application/pdf"},
    }
    metadata = extract_onedrive_metadata(file)
    assert metadata == {
        "id": "f1", "name": "report.pdf", "mime_type": "application/pdf", "size": 104857600,
        "created_at": "2026-01-01T00:00:00Z", "modified_at": "2026-01-02T00:00:00Z",
        "web_url": "https://onedrive.live.com/f1",
    }


def test_extract_onedrive_metadata_handles_a_real_folder_with_no_file_facet():
    """Real Graph API detail: a real folder has no `file` facet at all
    (its own `mimeType` lives nowhere)."""
    metadata = extract_onedrive_metadata({"id": "d1", "name": "My Folder", "folder": {"childCount": 0}})
    assert metadata["mime_type"] is None


# --------------------------------------------------------- should_include_onedrive_file --

def test_should_include_onedrive_file_excludes_real_folders():
    assert should_include_onedrive_file({"name": "sub", "folder": {"childCount": 1}}, None) is False


def test_should_include_onedrive_file_matches_by_real_extension():
    patterns = settings.onedrive_include_patterns_list
    assert should_include_onedrive_file({"name": "report.pdf", "file": {"mimeType": "application/pdf"}}, patterns) is True
    assert should_include_onedrive_file({"name": "photo.png", "file": {"mimeType": "image/png"}}, patterns) is False


def test_should_include_onedrive_file_enforces_the_real_size_cap(monkeypatch):
    """Validation criterion / vision critique Q4: un fichier trop gros
    est rejeté."""
    monkeypatch.setattr(settings, "ONEDRIVE_MAX_FILE_SIZE", 1000)
    small = {"name": "a.pdf", "size": 500, "file": {"mimeType": "application/pdf"}}
    big = {"name": "b.pdf", "size": 5000, "file": {"mimeType": "application/pdf"}}
    assert should_include_onedrive_file(small, None) is True
    assert should_include_onedrive_file(big, None) is False


def test_should_include_onedrive_file_with_no_size_field_is_not_rejected_on_size_alone():
    assert should_include_onedrive_file({"name": "a.pdf", "file": {"mimeType": "application/pdf"}}, None) is True
