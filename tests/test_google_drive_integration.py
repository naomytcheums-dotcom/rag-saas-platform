"""
Partie 2.1.14 -- orchestration tests for api/security/documents.py's own
process_google_drive.

**Deliberately NOT a real-network test file, unlike its GitHub-named
counterparts** (tests/test_github_integration.py,
tests/test_sitemap_integration.py) -- see tests/test_google_drive_extraction_integration.py's
own module docstring for why: no real Google OAuth credentials are
available to this automated session, and provisioning one would need a
real, interactive browser consent flow this session cannot responsibly
perform. What's tested here instead is process_google_drive's own real
ORCHESTRATION logic (resolve file-vs-folder, list, filter, cap,
authenticate, fan out) against a REALISTIC, hand-built simulation of
the real Google Drive API's own real response shapes (confirmed live,
see api/services/google_drive_extraction.py's own module docstring) --
`httpx.MockTransport` again, the same "real library behavior, fake
network" split every prior fast-tier test file in this codebase uses.

`process_google_drive_files` (the next real layer -- per-file Celery
dispatch) is monkeypatched to simply CAPTURE what it is called with,
the same established boundary as tests/test_github_integration.py's
own identical reasoning.
"""

import uuid
from unittest.mock import patch

import httpx

import api.services.google_drive_extraction as google_drive_extraction
from api.config import settings
from api.security.documents import process_google_drive
from api.services.google_drive_extraction import GOOGLE_DRIVE_FOLDER_MIME_TYPE, _access_token_cache


def _patch_drive_client(monkeypatch, handler):
    monkeypatch.setattr(google_drive_extraction, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(settings, "GOOGLE_DRIVE_REFRESH_TOKEN", "fake-refresh-token")
    _access_token_cache.clear()


def _oauth_or(real_handler):
    """Every real orchestration run authenticates first -- wraps a
    handler so the OAuth token endpoint is always answered the same
    real, successful way, and only Drive API calls reach `real_handler`."""
    def handler(request):
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "fake-access-token", "expires_in": 3600})
        return real_handler(request)

    return handler


def _patch_process_google_drive_files(captured):
    def _capture(organization_id, workspace_id, file_ids, created_by):
        captured["organization_id"] = organization_id
        captured["workspace_id"] = workspace_id
        captured["file_ids"] = file_ids
        captured["created_by"] = created_by
        return len(file_ids)

    return patch("api.security.documents.process_google_drive_files", side_effect=_capture)


async def test_process_google_drive_imports_a_real_shaped_folders_children(monkeypatch):
    """Validation criterion: l'import d'un dossier fonctionne, les
    fichiers sont filtrés par extension -- a real subfolder is
    excluded, not recursed into (this module's own stated scope
    limitation)."""
    def handler(request):
        if request.url.path == "/drive/v3/files/folder-1":
            return httpx.Response(200, json={"id": "folder-1", "name": "Reports", "mimeType": GOOGLE_DRIVE_FOLDER_MIME_TYPE})
        if request.url.path == "/drive/v3/files":
            return httpx.Response(200, json={"files": [
                {"id": "f1", "name": "report.pdf", "mimeType": "application/pdf", "size": "1000"},
                {"id": "f2", "name": "Subfolder", "mimeType": GOOGLE_DRIVE_FOLDER_MIME_TYPE},
                {"id": "f3", "name": "notes.txt", "mimeType": "text/plain", "size": "200"},
            ]})
        return httpx.Response(404, json={"error": {"message": "not found"}})

    _patch_drive_client(monkeypatch, _oauth_or(handler))
    captured = {}
    organization_id, created_by = uuid.uuid4(), uuid.uuid4()

    with _patch_process_google_drive_files(captured):
        result = await process_google_drive(organization_id, None, "folder-1", None, 100, created_by)

    assert result == "completed"
    assert captured["organization_id"] == organization_id
    assert captured["created_by"] == created_by
    assert sorted(captured["file_ids"]) == ["f1", "f3"]


async def test_process_google_drive_imports_a_single_real_file_directly(monkeypatch):
    """Validation criterion: l'import d'un fichier fonctionne -- the
    route's own literal "accepte un dossier/fichier Drive" -- a
    `drive_id` that resolves to a real FILE, not a folder, is imported
    directly without a real listing call at all."""
    def handler(request):
        if request.url.path == "/drive/v3/files/single-file-1":
            return httpx.Response(200, json={"id": "single-file-1", "name": "report.pdf", "mimeType": "application/pdf", "size": "1000"})
        raise AssertionError("must not call the real listing endpoint for a single file")

    _patch_drive_client(monkeypatch, _oauth_or(handler))
    captured = {}

    with _patch_process_google_drive_files(captured):
        result = await process_google_drive(uuid.uuid4(), None, "single-file-1", None, 100, uuid.uuid4())

    assert result == "completed"
    assert captured["file_ids"] == ["single-file-1"]


async def test_process_google_drive_excludes_a_single_real_file_that_does_not_match_patterns(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"id": "single-file-1", "name": "photo.png", "mimeType": "image/png", "size": "1000"})

    _patch_drive_client(monkeypatch, _oauth_or(handler))
    captured = {}

    with _patch_process_google_drive_files(captured):
        result = await process_google_drive(uuid.uuid4(), None, "single-file-1", [".pdf"], 100, uuid.uuid4())

    assert result == "completed"
    assert captured["file_ids"] == []


async def test_process_google_drive_enforces_a_real_max_files_cap(monkeypatch):
    def handler(request):
        if request.url.path == "/drive/v3/files/folder-1":
            return httpx.Response(200, json={"id": "folder-1", "name": "Reports", "mimeType": GOOGLE_DRIVE_FOLDER_MIME_TYPE})
        return httpx.Response(200, json={"files": [
            {"id": f"f{i}", "name": f"file-{i}.pdf", "mimeType": "application/pdf", "size": "100"} for i in range(5)
        ]})

    _patch_drive_client(monkeypatch, _oauth_or(handler))
    captured = {}

    with _patch_process_google_drive_files(captured):
        await process_google_drive(uuid.uuid4(), None, "folder-1", None, 2, uuid.uuid4())

    assert len(captured["file_ids"]) == 2


async def test_process_google_drive_returns_failed_when_no_refresh_token_is_configured(monkeypatch):
    """Vision critique Q2's own answer -- no credential, no import, a
    real, honest, logged failure, never a crash."""
    monkeypatch.setattr(settings, "GOOGLE_DRIVE_REFRESH_TOKEN", None)
    result = await process_google_drive(uuid.uuid4(), None, "folder-1", None, 100, uuid.uuid4())
    assert result == "failed"


async def test_process_google_drive_returns_failed_for_a_real_shaped_auth_rejection(monkeypatch):
    """Vision critique Q4's own answer -- que se passe-t-il si le token
    expire (or is simply invalid/revoked): a real, logged failure."""
    def handler(request):
        return httpx.Response(401, json={"error": "invalid_grant", "error_description": "Token has been expired or revoked."})

    _patch_drive_client(monkeypatch, handler)  # NOT wrapped in _oauth_or -- the OAuth call itself is what fails here
    result = await process_google_drive(uuid.uuid4(), None, "folder-1", None, 100, uuid.uuid4())
    assert result == "failed"


async def test_process_google_drive_returns_failed_for_a_real_nonexistent_target(monkeypatch):
    def handler(request):
        return httpx.Response(404, json={"error": {"message": "File not found", "status": ""}})

    _patch_drive_client(monkeypatch, _oauth_or(handler))
    result = await process_google_drive(uuid.uuid4(), None, "this-drive-id-genuinely-does-not-exist", None, 100, uuid.uuid4())
    assert result == "failed"
