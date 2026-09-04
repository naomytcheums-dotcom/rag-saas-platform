"""
Partie 2.1.18 -- orchestration tests for api/security/documents.py's own
process_onedrive.

**Deliberately NOT a real-network test file, unlike its GitHub-named
counterparts** -- see tests/test_onedrive_extraction_integration.py's
own module docstring for why: no real Microsoft/Azure credentials are
available to this automated session, and provisioning one would need a
real, interactive browser consent flow this session cannot responsibly
perform. What's tested here instead is process_onedrive's own real
ORCHESTRATION logic (resolve file-vs-folder, list, filter, cap,
authenticate, fan out) against a REALISTIC, hand-built simulation of
the real Microsoft Graph API's own real response shapes (confirmed
live, see api/services/onedrive_extraction.py's own module docstring)
-- `httpx.MockTransport` again, the same "real library behavior, fake
network" split every prior fast-tier test file in this codebase uses.

`process_onedrive_files` (the next real layer -- per-file Celery
dispatch) is monkeypatched to simply CAPTURE what it is called with,
the same established boundary as tests/test_google_drive_integration.py's
own identical reasoning.
"""

import uuid
from unittest.mock import patch

import httpx

import api.services.onedrive_extraction as onedrive_extraction
from api.config import settings
from api.security.documents import process_onedrive
from api.services.onedrive_extraction import _access_token_cache


def _patch_onedrive_client(monkeypatch, handler):
    monkeypatch.setattr(onedrive_extraction, "_client", lambda *args, **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(settings, "ONEDRIVE_REFRESH_TOKEN", "fake-refresh-token")
    _access_token_cache.clear()


def _oauth_or(real_handler):
    """Every real orchestration run authenticates first -- wraps a
    handler so the token endpoint is always answered the same real,
    successful way, and only Graph API calls reach `real_handler`."""
    def handler(request):
        if request.url.host == "login.microsoftonline.com":
            return httpx.Response(200, json={"access_token": "fake-access-token", "expires_in": 3600})
        return real_handler(request)

    return handler


def _patch_process_onedrive_files(captured):
    def _capture(organization_id, workspace_id, file_ids, created_by):
        captured["organization_id"] = organization_id
        captured["workspace_id"] = workspace_id
        captured["file_ids"] = file_ids
        captured["created_by"] = created_by
        return len(file_ids)

    return patch("api.security.documents.process_onedrive_files", side_effect=_capture)


async def test_process_onedrive_imports_a_real_shaped_folders_children(monkeypatch):
    """Validation criterion: l'import d'un dossier fonctionne, les
    fichiers sont filtrés par extension -- a real subfolder is
    excluded, not recursed into (this module's own stated scope
    limitation)."""
    def handler(request):
        if request.url.path == "/v1.0/me/drive/items/folder-1":
            return httpx.Response(200, json={"id": "folder-1", "name": "Reports", "folder": {"childCount": 3}})
        if request.url.path == "/v1.0/me/drive/items/folder-1/children":
            return httpx.Response(200, json={"value": [
                {"id": "f1", "name": "report.pdf", "size": 1000, "file": {"mimeType": "application/pdf"}},
                {"id": "f2", "name": "Subfolder", "folder": {"childCount": 1}},
                {"id": "f3", "name": "notes.txt", "size": 200, "file": {"mimeType": "text/plain"}},
            ]})
        return httpx.Response(404, json={"error": {"code": "itemNotFound", "message": "not found"}})

    _patch_onedrive_client(monkeypatch, _oauth_or(handler))
    captured = {}
    organization_id, created_by = uuid.uuid4(), uuid.uuid4()

    with _patch_process_onedrive_files(captured):
        result = await process_onedrive(organization_id, None, "folder-1", None, 100, created_by)

    assert result == "completed"
    assert captured["organization_id"] == organization_id
    assert captured["created_by"] == created_by
    assert sorted(captured["file_ids"]) == ["f1", "f3"]


async def test_process_onedrive_imports_a_single_real_file_directly(monkeypatch):
    """Validation criterion: l'import d'un fichier fonctionne -- the
    route's own literal "accepte un dossier/fichier OneDrive" -- a
    `folder_id` that resolves to a real FILE, not a folder, is imported
    directly without a real listing call at all."""
    def handler(request):
        if request.url.path == "/v1.0/me/drive/items/single-file-1":
            return httpx.Response(200, json={"id": "single-file-1", "name": "report.pdf", "size": 1000, "file": {"mimeType": "application/pdf"}})
        raise AssertionError("must not call the real listing endpoint for a single file")

    _patch_onedrive_client(monkeypatch, _oauth_or(handler))
    captured = {}

    with _patch_process_onedrive_files(captured):
        result = await process_onedrive(uuid.uuid4(), None, "single-file-1", None, 100, uuid.uuid4())

    assert result == "completed"
    assert captured["file_ids"] == ["single-file-1"]


async def test_process_onedrive_excludes_a_single_real_file_that_does_not_match_patterns(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"id": "single-file-1", "name": "photo.png", "size": 1000, "file": {"mimeType": "image/png"}})

    _patch_onedrive_client(monkeypatch, _oauth_or(handler))
    captured = {}

    with _patch_process_onedrive_files(captured):
        result = await process_onedrive(uuid.uuid4(), None, "single-file-1", [".pdf"], 100, uuid.uuid4())

    assert result == "completed"
    assert captured["file_ids"] == []


async def test_process_onedrive_enforces_a_real_max_files_cap(monkeypatch):
    def handler(request):
        if request.url.path == "/v1.0/me/drive/items/folder-1":
            return httpx.Response(200, json={"id": "folder-1", "name": "Reports", "folder": {"childCount": 5}})
        return httpx.Response(200, json={"value": [
            {"id": f"f{i}", "name": f"file-{i}.pdf", "size": 100, "file": {"mimeType": "application/pdf"}} for i in range(5)
        ]})

    _patch_onedrive_client(monkeypatch, _oauth_or(handler))
    captured = {}

    with _patch_process_onedrive_files(captured):
        await process_onedrive(uuid.uuid4(), None, "folder-1", None, 2, uuid.uuid4())

    assert len(captured["file_ids"]) == 2


async def test_process_onedrive_returns_failed_when_no_refresh_token_is_configured(monkeypatch):
    """Vision critique Q2's own answer -- no credential, no import, a
    real, honest, logged failure, never a crash."""
    monkeypatch.setattr(settings, "ONEDRIVE_REFRESH_TOKEN", None)
    result = await process_onedrive(uuid.uuid4(), None, "folder-1", None, 100, uuid.uuid4())
    assert result == "failed"


async def test_process_onedrive_returns_failed_for_a_real_shaped_auth_rejection(monkeypatch):
    """Vision critique Q4's own answer -- que se passe-t-il si le token
    expire (or is simply invalid/revoked): a real, logged failure."""
    def handler(request):
        return httpx.Response(400, json={"error": "invalid_grant", "error_description": "AADSTS9002313: Invalid request. Request is malformed or invalid."})

    _patch_onedrive_client(monkeypatch, handler)  # NOT wrapped in _oauth_or -- the token call itself is what fails here
    result = await process_onedrive(uuid.uuid4(), None, "folder-1", None, 100, uuid.uuid4())
    assert result == "failed"


async def test_process_onedrive_returns_failed_for_a_real_nonexistent_target(monkeypatch):
    def handler(request):
        return httpx.Response(404, json={"error": {"code": "itemNotFound", "message": "The resource could not be found."}})

    _patch_onedrive_client(monkeypatch, _oauth_or(handler))
    result = await process_onedrive(uuid.uuid4(), None, "this-item-id-genuinely-does-not-exist", None, 100, uuid.uuid4())
    assert result == "failed"
