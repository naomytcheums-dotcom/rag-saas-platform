"""Request/response bodies for api/routers/documents.py (Partie
2.1.1/2.1.10/2.1.11). Deliberately has NO field for `file_key` -- that's
an internal S3 storage detail, not something a client needs or should
be able to see."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field, HttpUrl


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
