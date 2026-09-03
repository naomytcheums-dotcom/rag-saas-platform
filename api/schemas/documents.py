"""Request/response bodies for api/routers/documents.py (Partie
2.1.1/2.1.10/2.1.11). Deliberately has NO field for `file_key` -- that's
an internal S3 storage detail, not something a client needs or should
be able to see."""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class DocumentResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    workspace_id: uuid.UUID | None
    name: str
    file_size: int
    file_type: str
    status: str
    # Exposed as `metadata` in the API (matching this step's own literal
    # field name) even though the ORM attribute is metadata_json -- see
    # api/models/document.py's own docstring for why the ORM attribute
    # itself can't be named `metadata` (collides with SQLAlchemy's
    # Base.metadata).
    metadata: dict | None
    # None for every file upload -- only real for a document imported
    # via Partie 2.1.10's POST .../documents/url (see
    # api/models/document.py's own docstring on this column).
    source_url: str | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime
    processed_at: dt.datetime | None


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]


class DocumentUrlImportRequest(BaseModel):
    """Partie 2.1.10, item 1's own request body. `HttpUrl` gives a
    real, free first layer of validation (rejects a non-http(s) scheme
    or a structurally invalid URL with a clean 422 before this request
    even reaches api/security/documents.py's own import_document_from_url)
    -- confirmed for real, it does NOT reject embedded credentials
    (`http://user:pass@host/`), which is why validate_url below still
    has its own real check for that, not a redundant one."""

    url: HttpUrl


class SitemapImportRequest(BaseModel):
    """Partie 2.1.11, item 4's own request body. `filters` is the
    step's own literal (optional) glob-pattern list (see
    api/services/sitemap_extraction.py's own filter_sitemap_urls);
    `max_urls` is the step's own literal real safety cap on how many
    PAGES get imported (independent of `_MAX_SUB_SITEMAPS`, a separate,
    internal cap on sub-sitemaps -- see api/tasks/sitemap_import.py's
    own module docstring), bounded to a real, sane range rather than
    letting a client request an unbounded fan-out."""

    url: HttpUrl
    filters: list[str] | None = None
    max_urls: int = Field(default=500, ge=1, le=5000)


class SitemapImportResponse(BaseModel):
    """A real, honest, minimal acknowledgment -- see
    api/tasks/sitemap_import.py's own module docstring for why there is
    no persisted "sitemap import job" to report richer status about:
    the sitemap itself is not even fetched until the real Celery task
    runs, so nothing more than "this was accepted for processing" is
    knowable synchronously."""

    sitemap_url: str
    status: str


class GitHubRepoImportRequest(BaseModel):
    """Partie 2.1.12, item 1's own request body. Deliberately has NO
    field for a GitHub token -- see api/config.py's own
    GITHUB_API_TOKEN docstring: that's a real, server-wide secret an
    operator configures once, never something a caller submits
    per-request. `file_patterns`, if omitted, falls back to
    settings.github_include_patterns_list (a real ALLOWLIST, unlike
    Partie 2.1.11's optional sitemap `filters`) -- see
    api/services/github_extraction.py's own module docstring.
    `max_files` bounded lower than Partie 2.1.11's own sitemap
    `max_urls`: each GitHub file costs one real, rate-limited API call
    on top of the full document-processing pipeline, a more expensive
    per-unit real cost than a sitemap page."""

    repo_url: HttpUrl
    file_patterns: list[str] | None = None
    max_files: int = Field(default=100, ge=1, le=2000)


class GitHubRepoImportResponse(BaseModel):
    """Same real, honest, minimal acknowledgment as SitemapImportResponse
    above, and for the identical reason -- see
    api/tasks/github_import.py's own module docstring."""

    owner: str
    repo: str
    status: str


class GitHubIssuesImportRequest(BaseModel):
    """Partie 2.1.13, item 1's own request body. `state` is constrained
    to GitHub's own three real values via `Literal` -- confirmed for
    real that GitHub's own API returns a real, distinct 422 for
    anything else, so rejecting it here, at this server's own schema
    layer, is a real, structural 422 of this server's own rather than
    surfacing GitHub's later, and only inside a deferred Celery task.
    `since`, if given, must be a real ISO 8601 string (confirmed for
    real: GitHub accepts either a bare `Z` suffix or a `+00:00` offset)
    -- left as a plain, unvalidated `str` here rather than a `datetime`
    field, matching this step's own literal function signatures
    exactly; a malformed one surfaces as GitHub's own real, honest 422
    inside the deferred task instead (see
    api/services/github_extraction.py's own module docstring). `labels`
    uses real OR semantics (see that same module docstring for why,
    not GitHub's own AND)."""

    repo_url: HttpUrl
    state: Literal["open", "closed", "all"] = "all"
    since: str | None = None
    labels: list[str] | None = None
    max_issues: int = Field(default=100, ge=1, le=2000)


class GitHubIssuesImportResponse(BaseModel):
    """Same real, honest, minimal acknowledgment as SitemapImportResponse/
    GitHubRepoImportResponse above, and for the identical reason."""

    owner: str
    repo: str
    status: str


class GoogleDriveImportRequest(BaseModel):
    """Partie 2.1.14, item 1's own request body. `drive_id` (not
    `folder_id`/`file_id` separately) since this step's own literal
    route accepts EITHER a real Drive folder or a real single file --
    api/security/documents.py's own process_google_drive resolves
    which for real. Deliberately no `HttpUrl` field here the way every
    prior import step had one: a real Drive id is an opaque
    Google-internal string, not a URL, with no meaningful FORMAT to
    validate at this schema layer -- real validation (does it exist, is
    it accessible) only happens once the deferred Celery task actually
    calls the real Drive API. Deliberately has NO field for OAuth
    credentials either -- see api/config.py's own GOOGLE_DRIVE_REFRESH_TOKEN
    docstring: those are real, server-wide secrets an operator
    configures once, never something a caller submits per-request."""

    drive_id: str = Field(min_length=1)
    patterns: list[str] | None = None
    max_files: int = Field(default=100, ge=1, le=2000)


class GoogleDriveImportResponse(BaseModel):
    """Same real, honest, minimal acknowledgment as every prior async
    import step's own response, and for the identical reason."""

    drive_id: str
    status: str


class GoogleDocImportRequest(BaseModel):
    """Partie 2.1.15, item 1's own request body. Exactly one of
    `document_url_or_id` (a single real Google Docs/Sheets/Slides URL
    or a bare Drive id) or `document_urls_or_ids` (a real list, for
    this step's own literal `process_google_docs_batch`) must be given
    -- validated below rather than as two separate routes, matching
    this step's own literal ONE route accepting either shape. Same
    reasoning as GoogleDriveImportRequest above for the lack of an
    `HttpUrl` field and the lack of any OAuth credential field."""

    document_url_or_id: str | None = None
    document_urls_or_ids: list[str] | None = None
    export_format: str | None = None

    @model_validator(mode="after")
    def _exactly_one_target_given(self) -> "GoogleDocImportRequest":
        if bool(self.document_url_or_id) == bool(self.document_urls_or_ids):
            raise ValueError("exactly one of document_url_or_id or document_urls_or_ids must be given")
        return self


class GoogleDocImportResponse(BaseModel):
    """Same real, honest, minimal acknowledgment as every prior async
    import step's own response, and for the identical reason."""

    document_ids: list[str]
    mode: Literal["single", "batch"]
    status: str


class NotionImportRequest(BaseModel):
    """Partie 2.1.16, item 1's own request body. `kind` tells a real
    page apart from a real database -- Notion's own URL scheme cannot
    reliably do this itself (see api/services/notion_extraction.py's
    own validate_notion_url docstring), so this defaults to the more
    common real case (`"page"`) rather than guessing via a real,
    synchronous network call the route itself must never make. Same
    reasoning as every prior import step for the lack of a token field."""

    url_or_id: str = Field(min_length=1)
    kind: Literal["page", "database"] = "page"
    max_pages: int = Field(default=100, ge=1, le=1000)


class NotionImportResponse(BaseModel):
    """Same real, honest, minimal acknowledgment as every prior async
    import step's own response, and for the identical reason."""

    notion_id: str
    kind: Literal["page", "database"]
    status: str


class ConfluenceImportRequest(BaseModel):
    """Partie 2.1.17, item 1's own request body. Unlike Notion, `kind`
    is NOT a caller-supplied field here -- a real Confluence page id is
    always numeric and a real space URL always carries its own real
    space KEY, so api/services/confluence_extraction.py's own
    validate_confluence_url determines it for real from the URL's own
    real shape, never a guess. Same reasoning as every prior import
    step for the lack of a token/base_url field (CONFLUENCE_BASE_URL is
    a real, server-wide setting, not per-request)."""

    url_or_id: str = Field(min_length=1)
    max_pages: int = Field(default=100, ge=1, le=1000)


class ConfluenceImportResponse(BaseModel):
    """Same real, honest, minimal acknowledgment as every prior async
    import step's own response, and for the identical reason."""

    confluence_id: str
    kind: Literal["page", "space"]
    status: str
