"""
Partie 2.1.14 -- fetching files from a Google Drive folder (or a single
Drive file) via the real Google Drive API v3, for import into a
knowledge base, authenticated through a real, server-side OAuth 2.0
refresh-token flow. Uses a plain `httpx.AsyncClient` against Google's
own fixed API hosts, the same "trusted, fixed external API, no SSRF-
safe transport needed" reasoning as `api/services/github_extraction.py`.

**A fundamentally different auth shape from every prior import step**:
Partie 2.1.10-2.1.13 all authenticate (when they need to at all) with a
single, static, pre-issued credential threaded straight into a request
header. Google's OAuth 2.0 model has no equivalent static credential
for server-to-server API access -- `GOOGLE_DRIVE_REFRESH_TOKEN` (a
real, long-lived credential, see `api/config.py`'s own docstring for
how an operator obtains one) must be exchanged for a real, short-lived
(~1 hour) ACCESS token before every batch of real Drive API calls, and
that access token must be refreshed again once it expires.
`authenticate_drive` below does this exchange-and-cache dance -- see
its own docstring for the real, PROACTIVE design (vision critique Q4's
own "que se passe-t-il si le token expire" answer: refreshed before its
own real expiry, not only reacted to after a real 401).

**Honest, stated limitation on how much of this could be verified for
real**: unlike Partie 2.1.12/2.1.13 (where `gh auth token` provided a
real, usable GitHub credential in this very session), NO real Google
OAuth credentials were available here -- there is no equivalent
`gh`-style ambient credential for Google, and provisioning one would
mean registering a real Google Cloud OAuth client and completing a
real, interactive browser consent flow, well outside this session's
safe, automated scope (the same restraint Partie 2.1.1 already took
with `S3_DOCUMENTS_BUCKET_NAME`, never auto-provisioned). What COULD be
verified for real, live, without any valid credential, and was:

- `POST https://oauth2.googleapis.com/token` with an unregistered
  `client_id` returns a real, live 401:
  `{"error": "invalid_client", "error_description": "The OAuth client was not found."}`.
  A real, DIFFERENT rejection happens when `client_id` is missing from
  the request ENTIRELY (this codebase's own default, unconfigured
  state): a real, live 400
  `{"error": "invalid_request", "error_description": "Could not determine client ID from request."}`
  -- both confirmed live, a genuine additional finding.
- The Drive API itself returns a real, live 403
  (`{"error": {"code": 403, "status": "PERMISSION_DENIED", ...}}`) for
  NO `Authorization` header at all, and a real, live 401
  (`{"error": {"code": 401, "status": "UNAUTHENTICATED", ...}}`) for a
  real, present-but-invalid access token -- confirmed against both
  `GET .../files` (list) and `GET .../files/{id}` (get). This is
  Google's own real, NESTED error envelope shape
  (`{"error": {"code", "message", "status", ...}}`), genuinely
  different from every prior GitHub-shaped flat error
  (`{"message": ..., "documentation_url": ...}`) this codebase has
  handled so far -- `_raise_for_drive_response` below is shaped for
  this real, confirmed envelope, not guessed.

An invalid/expired/revoked refresh token against a REAL, registered
client is documented by Google (not independently triggered here, no
real registered client was available) to return a real, distinct
`400 {"error": "invalid_grant", "error_description": "Token has been expired or revoked."}`
-- mapped explicitly below on the strength of Google's own stable,
published OAuth 2.0 contract, not re-derived from a live test.

**A real, important Drive-specific finding, verified against Google's
own stable, published Drive API v3 documentation**: a real native
Google Workspace file (a real Google Doc/Sheet/Slide -- `mimeType`
starting with `application/vnd.google-apps.`, excluding the real
`application/vnd.google-apps.folder` case) has NO downloadable binary
content at all; Google's own documented Drive API behavior requires
the separate `files.export` endpoint with an explicit target MIME type
instead of a plain `alt=media` download, which fails with a real,
distinct error for this case. This step's own literal scope is real,
already-binary Drive files -- a real Google Doc/Sheet/Slide is
deliberately excluded here (`should_include_drive_file` below), Partie
2.1.15's own explicit, separate scope ("Google Docs API export ->
Markdown"), not something this step re-implements or half-supports.

**A real, stated scope limitation, not partial/broken behavior**:
recursion into real SUBFOLDERS is deliberately NOT implemented --
this step's own literal action items describe importing the given
folder's own real files (`list_drive_files(folder_id, ...)`), matching
Drive's own real `files.list` scope (direct children of one real
parent), not a Git-Trees-API-style full recursive walk (Drive's real
API has no single call equivalent to that; a true recursive walk would
cost one real API call PER real subfolder, an unbounded real fan-out
this step's own literal scope never asked for). A real subfolder
encountered in a real listing is simply excluded, the same way a real
native Google Doc is -- not silently mishandled, not partially walked.
"""

import logging
import time

import httpx

from api.config import settings
from api.services.url_fetching import USER_AGENT

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_DRIVE_API_BASE_URL = "https://www.googleapis.com/drive/v3"
_TIMEOUT_SECONDS = 15.0

_GOOGLE_WORKSPACE_MIME_PREFIX = "application/vnd.google-apps."
GOOGLE_DRIVE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

# Real, documented Drive API fields -- both `files.list` and `files.get`
# return only `id`/`name`/`mimeType` unless the real fields actually
# needed are explicitly requested via this real query parameter.
_DRIVE_FILE_FIELDS = "id, name, mimeType, size, modifiedTime, createdTime, webViewLink, parents"


class GoogleDriveAuthError(ValueError):
    """A real, distinguishable subclass of the same `ValueError` every
    other real failure in this module raises -- an expired, revoked, or
    otherwise invalid OAuth credential (refresh token OR access token),
    vision critique Q4's own "si le token expire" answer made
    programmatically distinguishable, the same shape as
    `api/services/github_extraction.py`'s own `GitHubRateLimitError`."""


class GoogleDriveRateLimitError(ValueError):
    """Same real, distinguishable-subclass shape as GitHubRateLimitError
    -- Drive's own real per-user rate limit, confirmed via its own
    documented `RATE_LIMIT_EXCEEDED`/`USER_RATE_LIMIT_EXCEEDED` real
    error status values."""


def _client() -> httpx.AsyncClient:
    """Same "one small factory function, easy to monkeypatch" shape as
    `api/services/url_fetching.py`/`github_extraction.py`'s own
    `_client()` -- the seam `tests/test_google_drive_extraction.py`
    patches with `httpx.MockTransport`."""
    return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)


def _headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}", "User-Agent": USER_AGENT}


def _raise_for_drive_response(response: httpx.Response, file_id: str | None = None) -> None:
    """Real status-code mapping for Drive's own real, NESTED error
    envelope -- see this module's own docstring for the real, live
    responses this was verified against."""
    if response.status_code < 400:
        return
    try:
        body = response.json()
        error = body.get("error", {})
        message = error.get("message", response.text) if isinstance(error, dict) else response.text
        status = error.get("status", "") if isinstance(error, dict) else ""
    except ValueError:
        message, status = response.text, ""

    target = f"Drive file '{file_id}'" if file_id else "this Drive request"
    if status in ("RATE_LIMIT_EXCEEDED", "USER_RATE_LIMIT_EXCEEDED"):
        raise GoogleDriveRateLimitError(f"Google Drive API rate limit exceeded for {target}: {message}")
    if response.status_code in (401, 403) and status in ("UNAUTHENTICATED", "PERMISSION_DENIED"):
        raise GoogleDriveAuthError(f"Google Drive API rejected the configured credentials for {target}: {message}")
    if response.status_code == 404:
        raise ValueError(f"{target} was not found, or is not accessible with the configured Google Drive credentials")
    response.raise_for_status()


# Real, in-memory per-worker-process cache -- refreshing a real Google
# access token is a real network round-trip; reusing it until shortly
# before its own real reported expiry avoids one for every single real
# Drive API call, the same "cache real, non-trivial state, not on every
# call" reasoning as `api/security/documents.py`'s own `_EMBEDDER_CACHE`.
# Keyed by the real refresh token, so distinct real credentials (a real,
# if unlikely, multi-tenant deployment) never share a cached access
# token that doesn't belong to them.
_access_token_cache: dict[str, tuple[str, float]] = {}
# A real, deliberate safety margin: refresh BEFORE the real access
# token's own reported expiry, not exactly at it -- avoids a real race
# where a token expires mid-flight between this check and the request
# that actually uses it.
_TOKEN_REFRESH_MARGIN_SECONDS = 60


async def authenticate_drive(token: str) -> str:
    """
    Item 3's literal function -- `token` here is the real, long-lived
    REFRESH token (see `api/config.py`'s own `GOOGLE_DRIVE_REFRESH_TOKEN`
    docstring), exchanged for a real, short-lived access token every
    other real Drive API call in this module actually needs. Real,
    PROACTIVELY cached and refreshed before its own real expiry --
    vision critique Q4's own answer -- rather than only reacted to
    after a real 401 already happened. `GOOGLE_DRIVE_CLIENT_ID`/
    `SECRET` are read directly from settings here (not threaded through
    as parameters) -- matching this step's own literal one-argument
    signature exactly, and consistent with `GITHUB_API_TOKEN`'s own
    "never thread a real secret through more places than necessary"
    security reasoning.
    """
    cached = _access_token_cache.get(token)
    if cached is not None:
        access_token, expires_at = cached
        if time.time() < expires_at - _TOKEN_REFRESH_MARGIN_SECONDS:
            return access_token

    async with _client() as client:
        response = await client.post(_TOKEN_URL, data={
            "grant_type": "refresh_token", "refresh_token": token,
            "client_id": settings.GOOGLE_DRIVE_CLIENT_ID, "client_secret": settings.GOOGLE_DRIVE_CLIENT_SECRET,
        })

    if response.status_code != 200:
        try:
            body = response.json()
        except ValueError:
            body = {}
        error = body.get("error", "unknown_error")
        raise GoogleDriveAuthError(
            f"Google OAuth token refresh failed ({error}): {body.get('error_description', response.text)}"
        )

    body = response.json()
    access_token = body["access_token"]
    _access_token_cache[token] = (access_token, time.time() + body.get("expires_in", 3600))
    return access_token


def should_include_drive_file(file: dict, patterns: list[str] | None) -> bool:
    """
    Item 4's literal function -- a real ALLOWLIST (same reasoning as
    Partie 2.1.12's own `should_include_file`): an arbitrary Drive
    folder can hold real content (images, videos, real native Google
    Docs/Sheets/Slides with no downloadable binary at all) this
    pipeline cannot meaningfully process as text. Real FOLDERS and real
    native GOOGLE WORKSPACE files are ALWAYS excluded here, regardless
    of `patterns` -- see this module's own docstring for why (a real
    folder has no content of its own; a real native Google Doc needs
    Partie 2.1.15's own separate export handling). Real file SIZE is
    also enforced here (`GOOGLE_DRIVE_MAX_FILE_SIZE`) -- Drive's own
    `size` field is trustworthy first-party metadata (unlike an
    arbitrary external URL's `Content-Length`, see
    `api/services/url_fetching.py`'s own docstring for why THAT one
    can't be trusted), so no separate streamed-byte-count safety net is
    needed the way that module needed one.
    """
    mime_type = file.get("mimeType", "")
    if mime_type == GOOGLE_DRIVE_FOLDER_MIME_TYPE or mime_type.startswith(_GOOGLE_WORKSPACE_MIME_PREFIX):
        return False
    if patterns:
        name = file.get("name", "")
        if not any(name.lower().endswith(pattern.lower()) for pattern in patterns):
            return False
    size = file.get("size")
    if size is not None and int(size) > settings.GOOGLE_DRIVE_MAX_FILE_SIZE:
        return False
    return True


# Real safety cap on how many real PAGES of one folder's own direct
# children `list_drive_files` will fetch (1,000 real files/page, Drive's
# own real per-request maximum) -- protects the FETCH phase itself,
# independent of `process_google_drive`'s own `max_files` (applied
# afterward, at the orchestration level -- same "filter before cap"
# ordering Partie 2.1.11/2.1.12/2.1.13 already established).
_MAX_DRIVE_LIST_PAGES = 50


async def list_drive_files(folder_id: str, token: str, patterns: list[str] | None = None) -> list[dict]:
    """
    Item 3's literal function -- lists one real Drive folder's DIRECT
    children (real pagination via Drive's own real `nextPageToken`),
    already filtered through `should_include_drive_file` (real
    folders/native-Google-Workspace-files/oversized-files/pattern-
    mismatches all excluded here, not left for a caller to redo).
    `token` here is a real, already-exchanged ACCESS token (this
    function makes no OAuth call of its own -- `process_google_drive`
    below calls `authenticate_drive` once and reuses the result for
    every real Drive API call in one real import run).
    """
    query = f"'{folder_id}' in parents and trashed = false"
    matched: list[dict] = []
    page_token = None
    async with _client() as client:
        for _ in range(_MAX_DRIVE_LIST_PAGES):
            params = {"q": query, "fields": f"nextPageToken, files({_DRIVE_FILE_FIELDS})", "pageSize": 1000}
            if page_token:
                params["pageToken"] = page_token
            response = await client.get(f"{_DRIVE_API_BASE_URL}/files", headers=_headers(token), params=params)
            _raise_for_drive_response(response)
            body = response.json()
            matched.extend(item for item in body.get("files", []) if should_include_drive_file(item, patterns))
            page_token = body.get("nextPageToken")
            if not page_token:
                break
    return matched


async def get_drive_file(file_id: str, token: str) -> dict:
    """NOT one of this step's own literal functions -- a real,
    deliberate addition needed to determine whether a real `drive_id`
    given to this step's own literal route is a real FOLDER or a real
    FILE (the route accepts either) before deciding whether to list
    its children or import it directly (`process_google_drive` below).
    Also the real per-file metadata fetch `import_and_process_google_drive_file`
    uses before downloading."""
    async with _client() as client:
        response = await client.get(
            f"{_DRIVE_API_BASE_URL}/files/{file_id}", headers=_headers(token), params={"fields": _DRIVE_FILE_FIELDS},
        )
    _raise_for_drive_response(response, file_id)
    return response.json()


async def download_drive_file(file_id: str, token: str) -> bytes:
    """Item 3's literal function -- real binary content via Drive's
    own real `alt=media` parameter. A real native Google Workspace file
    slipping through (should_include_drive_file is meant to exclude
    these before this function is ever called, making this a safety
    net, not the normal path) fails here with a real, distinct Drive
    error (`400`/`403 fileNotDownloadable` in Google's own real,
    documented behavior), never silently returning something
    meaningless."""
    async with _client() as client:
        response = await client.get(
            f"{_DRIVE_API_BASE_URL}/files/{file_id}", headers=_headers(token), params={"alt": "media"},
        )
    _raise_for_drive_response(response, file_id)
    return response.content


def extract_drive_metadata(file: dict) -> dict:
    """Item 3's literal function -- nom, type, taille, date. Real Drive
    API detail: `size` is returned as a real STRING in the JSON body
    (Google's own convention for real int64-range fields, to avoid
    precision loss in a JSON number) -- converted to a real Python int
    here; `None` for a real native Google Workspace file, which
    genuinely has no `size` field at all (no downloadable binary to
    measure)."""
    return {
        "id": file.get("id"),
        "name": file.get("name"),
        "mime_type": file.get("mimeType"),
        "size": int(file["size"]) if file.get("size") is not None else None,
        "created_at": file.get("createdTime"),
        "modified_at": file.get("modifiedTime"),
        "web_view_link": file.get("webViewLink"),
    }
