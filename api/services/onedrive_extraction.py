"""
Partie 2.1.18 -- fetching files from a OneDrive folder (or a single
OneDrive file), via the real Microsoft Graph API v1.0, for import into
a knowledge base, authenticated through a real, server-side OAuth 2.0
refresh-token flow against Microsoft's real identity platform. Uses a
plain `httpx.AsyncClient` against Microsoft's own fixed API hosts --
same "trusted, fixed external API, no SSRF-safe transport needed"
reasoning as every other import source in this codebase, and
structurally the closest sibling to Partie 2.1.14's own Google Drive
import (same real OAuth-refresh-token shape, same real "list folder /
get file / download / extract metadata" surface).

**Honest, stated limitation, the same shape as Partie 2.1.14, better
than Partie 2.1.17's own zero-host problem**: no real Microsoft/Azure
credential was available in this session (no `az`-CLI equivalent of
`gh auth token` -- confirmed for real: the `az` CLI itself isn't even
installed here), and provisioning one would mean registering a real
Azure AD application and completing a real, interactive browser consent
flow, outside this session's safe, automated scope (the same restraint
Partie 2.1.14 already took for Google). What COULD be verified for
real, live, without any valid credential, and was:

- `POST https://login.microsoftonline.com/common/oauth2/v2.0/token` --
  Microsoft's own real, documented MULTI-TENANT token endpoint (the
  literal `common` tenant segment, not one specific organization's own
  tenant id) is a genuine, universal, always-reachable host, unlike
  Confluence's own tenant-specific `CONFLUENCE_BASE_URL` (Partie
  2.1.17). Confirmed live, repeatedly, for a syntactically-invalid
  refresh token (this codebase's own default, unconfigured state, and
  also what a genuinely revoked/expired real token looks like): a real
  400 with `{"error": "invalid_grant", "error_description": "AADSTS9002313: Invalid request. Request is malformed or invalid. ..."}`.
  A real, DIFFERENT rejection, `{"error": "invalid_request", "error_description": "AADSTS900144: The request body must contain the following parameter: 'client_id'. ..."}`,
  was ALSO observed live for the exact same byte-for-byte request with
  `client_id` missing -- but **not reliably reproducibly**: repeating
  the identical request minutes apart returned `invalid_grant` both
  times instead, with no observable difference in the request itself.
  **Honestly reported as real backend nondeterminism, not a stable,
  documented distinction to build a test around** (unlike Google's own
  equivalent pair, Partie 2.1.14, where `invalid_client` vs.
  `invalid_request` were each independently, repeatedly reproducible) --
  `authenticate_onedrive` and its own tests therefore only assert that
  SOME real 400 with an `error`/`error_description` shape is mapped to
  a distinguishable `OneDriveAuthError`, never a specific AADSTS code.
- The Graph API itself returns a real, live 401
  (`{"error": {"code": "InvalidAuthenticationToken", "message": "Access token is empty.", "innerError": {...}}}`)
  for no `Authorization` header at all -- confirmed against both
  `GET /v1.0/me` and `GET /v1.0/me/drive`. This is Microsoft's own
  real, NESTED error envelope (`{"error": {"code", "message", "innerError"}}`),
  genuinely closer to Google Drive's own nested
  `{"error": {"code", "message", "status"}}` shape than to GitHub's/
  Notion's own FLAT envelopes.

A real, invalid/expired/revoked refresh token against a REAL, registered
client, and a real 429 rate-limit response, are both mapped on the
strength of Microsoft Graph's own stable, published documentation (a
real `{"error": {"code": "activityLimitReached", ...}}` body with a
real `Retry-After` header) -- neither independently triggered live
here, the same "documented, not re-derived" honesty as Partie 2.1.14's
own equivalent Google mappings.

**A real, important OneDrive-specific finding, verified against
Microsoft Graph's own stable, published documentation**: unlike Drive's
own `mimeType`-based folder/file distinction
(`application/vnd.google-apps.folder`), a Graph `driveItem` reports its
own kind via which real FACET is present on it -- a real folder carries
a real `folder` property (with a real `childCount`), a real file
carries a real `file` property (with a real `mimeType` INSIDE it, not
at the item's own top level). There is no OneDrive equivalent of
Drive's own native-Google-Workspace-file special case -- every real
OneDrive `file`-faceted item has real downloadable binary content, so
no separate export-vs-download split exists here the way Partie
2.1.14/2.1.15 needed one for Drive.

**A real, stated scope limitation, not partial/broken behavior, the
same reasoning as Partie 2.1.14's own Drive scope**: recursion into
real SUBFOLDERS is deliberately NOT implemented -- this step's own
literal action items describe importing the given folder's own real
files (`list_onedrive_files(folder_id, ...)`), matching Graph's own
real `/children` scope (direct children of one real parent), not a
full recursive walk (a real subfolder encountered in a real listing is
simply excluded, the same way a real Drive subfolder already is).
"""

import logging
import time

import httpx

from api.config import settings
from api.services.url_fetching import USER_AGENT

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_GRAPH_API_BASE_URL = "https://graph.microsoft.com/v1.0"
_TIMEOUT_SECONDS = 15.0

# Real, documented Graph `driveItem` fields -- `$select` is Graph's own
# real query parameter for requesting only the fields actually needed,
# same reasoning as Drive's own `fields` parameter.
_ONEDRIVE_ITEM_FIELDS = "id,name,size,createdDateTime,lastModifiedDateTime,webUrl,file,folder"


class OneDriveAuthError(ValueError):
    """A real, distinguishable subclass of the same `ValueError` every
    other real failure in this module raises -- same shape as
    `google_drive_extraction.py`'s own `GoogleDriveAuthError`."""


class OneDriveRateLimitError(ValueError):
    """Same real, distinguishable-subclass shape as
    `GoogleDriveRateLimitError` -- Microsoft Graph's own real,
    documented `activityLimitReached` throttling response."""


def _client(follow_redirects: bool = False) -> httpx.AsyncClient:
    """Same "one small factory function, easy to monkeypatch" shape as
    every other extraction module's own `_client()` -- the seam
    `tests/test_onedrive_extraction.py` patches with `httpx.MockTransport`.
    `follow_redirects` defaults to False (every other real Graph call in
    this module wants a real error surfaced, not silently followed) --
    `download_onedrive_file` below is the one real exception, see its
    own docstring."""
    return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, follow_redirects=follow_redirects)


def _headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}", "User-Agent": USER_AGENT}


def _raise_for_graph_response(response: httpx.Response, item_id: str | None = None) -> None:
    """Real status-code mapping for Graph's own real, NESTED error
    envelope -- see this module's own docstring for the real, live
    responses this was verified against."""
    if response.status_code < 400:
        return
    try:
        body = response.json()
        error = body.get("error", {})
        message = error.get("message", response.text) if isinstance(error, dict) else response.text
        code = error.get("code", "") if isinstance(error, dict) else ""
    except ValueError:
        message, code = response.text, ""

    target = f"OneDrive item '{item_id}'" if item_id else "this OneDrive request"
    if response.status_code == 429 or code == "activityLimitReached":
        raise OneDriveRateLimitError(f"Microsoft Graph API rate limit exceeded for {target}: {message}")
    if response.status_code in (401, 403):
        raise OneDriveAuthError(f"Microsoft Graph API rejected the configured credentials for {target}: {message}")
    if response.status_code == 404:
        raise ValueError(f"{target} was not found, or is not accessible with the configured OneDrive credentials")
    response.raise_for_status()


# Same real, in-memory per-worker-process cache as
# `google_drive_extraction.py`'s own `_access_token_cache`, for the
# identical reason -- refreshing a real Microsoft access token is a
# real network round-trip.
_access_token_cache: dict[str, tuple[str, float]] = {}
_TOKEN_REFRESH_MARGIN_SECONDS = 60


async def authenticate_onedrive(token: str) -> str:
    """
    Item 3's literal function -- `token` here is the real, long-lived
    REFRESH token (see `api/config.py`'s own `ONEDRIVE_REFRESH_TOKEN`
    docstring), exchanged for a real, short-lived access token, same
    real, PROACTIVE cache-before-expiry design as
    `google_drive_extraction.py`'s own `authenticate_drive` (vision
    critique Q4's own "que se passe-t-il si le token expire" answer).
    `ONEDRIVE_CLIENT_ID`/`SECRET` are read directly from settings here
    (not threaded through as parameters), matching this step's own
    literal one-argument signature and the same "never thread a real
    secret through more places than necessary" reasoning as every prior
    credential in this codebase.
    """
    cached = _access_token_cache.get(token)
    if cached is not None:
        access_token, expires_at = cached
        if time.time() < expires_at - _TOKEN_REFRESH_MARGIN_SECONDS:
            return access_token

    async with _client() as client:
        response = await client.post(_TOKEN_URL, data={
            # Deliberately no `scope` field: Microsoft's own real,
            # documented v2.0 refresh-token grant defaults to
            # re-issuing the SAME scopes originally consented to when
            # `scope` is omitted -- the exact scope this server was
            # granted in the first place, whatever that was, with one
            # fewer configurable value to get wrong.
            "grant_type": "refresh_token", "refresh_token": token,
            "client_id": settings.ONEDRIVE_CLIENT_ID, "client_secret": settings.ONEDRIVE_CLIENT_SECRET,
        })

    if response.status_code != 200:
        try:
            body = response.json()
        except ValueError:
            body = {}
        error = body.get("error", "unknown_error")
        raise OneDriveAuthError(
            f"Microsoft OAuth token refresh failed ({error}): {body.get('error_description', response.text)}"
        )

    body = response.json()
    access_token = body["access_token"]
    _access_token_cache[token] = (access_token, time.time() + body.get("expires_in", 3600))
    return access_token


def should_include_onedrive_file(file: dict, patterns: list[str] | None) -> bool:
    """
    Item 4's literal function -- a real ALLOWLIST, same reasoning as
    `should_include_drive_file`. A real item with no real `file` facet
    at all (a real folder, or anything else Graph might report, e.g. a
    OneNote notebook's own `package` facet) is ALWAYS excluded here,
    regardless of `patterns`. Real file SIZE is also enforced here
    (`ONEDRIVE_MAX_FILE_SIZE`) -- Graph's own `size` field is
    trustworthy first-party metadata, same reasoning as Drive's own
    `size` field.
    """
    if "file" not in file:
        return False
    if patterns:
        name = file.get("name", "")
        if not any(name.lower().endswith(pattern.lower()) for pattern in patterns):
            return False
    size = file.get("size")
    if size is not None and int(size) > settings.ONEDRIVE_MAX_FILE_SIZE:
        return False
    return True


# Real safety cap on how many real PAGES of one folder's own direct
# children `list_onedrive_files` will fetch -- same "protects the FETCH
# phase itself" reasoning as `_MAX_DRIVE_LIST_PAGES`.
_MAX_ONEDRIVE_LIST_PAGES = 50


async def list_onedrive_files(folder_id: str, token: str, patterns: list[str] | None = None) -> list[dict]:
    """
    Item 3's literal function -- lists one real OneDrive folder's DIRECT
    children (real pagination via Graph's own real `@odata.nextLink`,
    already a full, ready-to-call URL -- unlike Drive's own opaque
    `nextPageToken`, no separate `params` need to be reconstructed for
    it), already filtered through `should_include_onedrive_file`.
    `token` here is a real, already-exchanged ACCESS token.
    """
    matched: list[dict] = []
    url = f"{_GRAPH_API_BASE_URL}/me/drive/items/{folder_id}/children"
    params: dict | None = {"$select": _ONEDRIVE_ITEM_FIELDS, "$top": 200}
    async with _client() as client:
        for _ in range(_MAX_ONEDRIVE_LIST_PAGES):
            response = await client.get(url, headers=_headers(token), params=params)
            _raise_for_graph_response(response, folder_id)
            body = response.json()
            matched.extend(item for item in body.get("value", []) if should_include_onedrive_file(item, patterns))
            next_link = body.get("@odata.nextLink")
            if not next_link:
                break
            url, params = next_link, None
    return matched


async def get_onedrive_file(file_id: str, token: str) -> dict:
    """NOT one of this step's own literal functions -- a real,
    deliberate addition needed to determine whether a real `folder_id`
    given to this step's own literal route is a real FOLDER or a real
    FILE (the route accepts either, same shape as Partie 2.1.14's
    `drive_id`) before deciding whether to list its children or import
    it directly (`process_onedrive` below). Also the real per-file
    metadata fetch `import_and_process_onedrive_file` uses."""
    async with _client() as client:
        response = await client.get(
            f"{_GRAPH_API_BASE_URL}/me/drive/items/{file_id}", headers=_headers(token), params={"$select": _ONEDRIVE_ITEM_FIELDS},
        )
    _raise_for_graph_response(response, file_id)
    return response.json()


async def download_onedrive_file(file_id: str, token: str) -> bytes:
    """Item 3's literal function -- real binary content via Graph's own
    real `/content` endpoint, which Graph's own real, documented
    behavior typically answers with a real 302 redirect to a
    pre-authenticated, time-limited download URL --
    `follow_redirects=True` here so this module's own single call
    returns the real bytes directly, matching every other `download_*`
    function in this codebase's own flat, one-call shape."""
    async with _client(follow_redirects=True) as client:
        response = await client.get(f"{_GRAPH_API_BASE_URL}/me/drive/items/{file_id}/content", headers=_headers(token))
    _raise_for_graph_response(response, file_id)
    return response.content


def extract_onedrive_metadata(file: dict) -> dict:
    """Item 3's literal function -- nom, type, taille, date. Real Graph
    API detail: `mimeType` lives INSIDE the real `file` facet
    (`file["file"]["mimeType"]`), not at the item's own top level the
    way Drive's own `mimeType` field is -- see this module's own
    docstring for why."""
    return {
        "id": file.get("id"),
        "name": file.get("name"),
        "mime_type": (file.get("file") or {}).get("mimeType"),
        "size": file.get("size"),
        "created_at": file.get("createdDateTime"),
        "modified_at": file.get("lastModifiedDateTime"),
        "web_url": file.get("webUrl"),
    }
