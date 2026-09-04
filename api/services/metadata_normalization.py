"""
Partie 2.2.5 -- normalizing each format's own real, already-extracted
metadata (`api/services/document_extraction.py`'s own per-format
`extract_*_metadata` functions, already stored verbatim in
`Document.metadata_json` by `process_document` since Partie 2.1.1) into
one common, cross-format shape: real `title`/`author`/`created_date`/
`keywords`, when a given format's own real metadata actually carries an
equivalent -- never fabricated when a format genuinely has no such
concept at all (CSV/JSON/XML/TXT have no real author/title/date/
keywords, and this module honestly reports `None`/`[]` for those,
rather than inventing one).

**Deliberately does NOT touch `process_document`'s own already-stored
`Document.metadata_json` at all** -- this is a real, additive READ-time
transformation (`api/routers/documents.py`'s own
`GET /documents/{document_id}/metadata` route calls it), not a change
to the shared, heavily-used core extraction pipeline every format since
Partie 2.1.1 already relies on. The real, per-format RAW dict this
module reads is untouched; it is also returned unchanged under this
function's own `"raw"` key, for any caller that needs a genuinely
format-specific field (a real PDF `page_count`, a real CSV
`row_count`, a real XML `root` tag, ...) this common shape doesn't
carry.

**Real, per-format key mapping this module is built against** (see
each extractor's own docstring for the full story):
- PDF (`extract_pdf_metadata`): PyMuPDF's own raw Info-dictionary keys
  -- `title`/`author` already match this module's own common names;
  `creationDate` is the PDF spec's own real, raw date STRING
  (`D:YYYYMMDDHHmmSS±HH'mm'`, ISO 32000-1 section 7.9.4), parsed for
  real here, not just passed through; `keywords` is one real,
  comma-or-semicolon-separated string, split for real here. `creator`
  (the authoring SOFTWARE, e.g. "Microsoft Word", per the PDF spec's
  own distinct meaning) is deliberately NEVER treated as an author
  fallback -- a real, substantive difference, not an oversight.
- DOCX (`extract_docx_metadata`): `title`/`author` already match;
  `created` is already real ISO 8601; `keywords` is OOXML's own real,
  semicolon-separated "Tags" core property, split for real here.
- Markdown (`extract_markdown_metadata`): whatever the document's own
  real YAML frontmatter declares, merged at the top level -- `title`/
  `author`/`date`/`tags`, each present only if the document's own
  author actually wrote it; `tags` may legitimately already be a real
  YAML list, or a bare string, both handled here.
- HTML (`extract_html_metadata`): `title`/`author`/`date`/`keywords`
  already match (the real, standard `<meta name="keywords">` tag,
  comma-separated).
- EPUB (`extract_epub_metadata`): `title` matches; `author` is already
  a real list (a real book can have several); `subject` (Dublin Core's
  own real name for a book's genre/topic tags) is this format's own
  real keywords equivalent, also a real list.
- CSV/JSON/XML/TXT: no real author/title/date/keywords concept exists
  in any of these formats at all -- every common field is honestly
  `None`/`[]`, never guessed.
"""

import re

from api.services.document_extraction import DOCX_CONTENT_TYPE, EPUB_CONTENT_TYPE, PDF_CONTENT_TYPE

# ISO 32000-1 section 7.9.4's own real PDF date string format.
_PDF_DATE_RE = re.compile(
    r"^D:(?P<year>\d{4})(?P<month>\d{2})?(?P<day>\d{2})?"
    r"(?P<hour>\d{2})?(?P<minute>\d{2})?(?P<second>\d{2})?"
)

_KEYWORD_SPLIT_RE = re.compile(r"[;,]")


def _parse_pdf_date(value: str | None) -> str | None:
    """Real, deterministic parsing of the PDF spec's own `D:...` date
    format into a real ISO 8601 string -- returns `None` for a missing,
    empty, or genuinely unparseable value (never a fabricated guess)."""
    if not value:
        return None
    match = _PDF_DATE_RE.match(value)
    if not match:
        return None
    year = match.group("year")
    month = match.group("month") or "01"
    day = match.group("day") or "01"
    hour = match.group("hour") or "00"
    minute = match.group("minute") or "00"
    second = match.group("second") or "00"
    return f"{year}-{month}-{day}T{hour}:{minute}:{second}"


def _split_keyword_string(value: str) -> list[str]:
    """Real, shared helper -- PDF/DOCX/HTML all store keywords as one
    real, comma-or-semicolon-separated string (never a native list);
    splits and trims, dropping empty entries."""
    return [part.strip() for part in _KEYWORD_SPLIT_RE.split(value) if part.strip()]


def _normalize_keywords(value) -> list[str]:
    """A real value already returned as a list (Markdown frontmatter's
    own `tags`, EPUB's own `subject`) is used as-is (each entry
    stringified defensively); a real string is split via
    `_split_keyword_string`; anything falsy is a real, honest empty
    list, never a guess."""
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return _split_keyword_string(str(value))


def _normalize_author(value):
    """EPUB's own real `author` is already a list (a real book can
    have several) -- kept as one; every other format's own real
    `author` is a bare string or `None` -- kept as-is, never forced
    into a single-item list, since that would be a fabricated shape
    change for formats whose real metadata never distinguishes
    multi-author works."""
    return value


def normalize_document_metadata(raw_metadata: dict | None, file_type: str) -> dict:
    """
    Item 1's own literal ask ("détection automatique des métadonnées
    communes... normaliser dans un format unifié") -- maps a document's
    own already-extracted, per-format `raw_metadata` (Document.metadata_json,
    already real and stored since this document was first processed)
    into one common shape: `{"title", "author", "created_date", "keywords"}`,
    plus the original, completely untouched dict under `"raw"`.
    """
    metadata = raw_metadata or {}

    title = metadata.get("title")
    author = _normalize_author(metadata.get("author"))

    if file_type == PDF_CONTENT_TYPE:
        created_date = _parse_pdf_date(metadata.get("creationDate"))
        keywords = _normalize_keywords(metadata.get("keywords"))
    elif file_type == DOCX_CONTENT_TYPE:
        created_date = metadata.get("created")
        keywords = _normalize_keywords(metadata.get("keywords"))
    elif file_type == EPUB_CONTENT_TYPE:
        created_date = metadata.get("date")
        keywords = _normalize_keywords(metadata.get("subject"))
    else:
        # HTML already uses "date"/"keywords" as its own real key
        # names; Markdown frontmatter's own real, conventional key is
        # "tags", not "keywords" (a real, deliberate distinction, not
        # an oversight -- checked first since a document could
        # theoretically declare both, however unlikely). CSV/JSON/XML/
        # TXT have neither concept at all, and honestly report
        # None/[] here via the same .get() fallback.
        created_date = metadata.get("date")
        keywords = _normalize_keywords(metadata.get("tags") or metadata.get("keywords"))

    return {
        "title": title,
        "author": author,
        "created_date": created_date,
        "keywords": keywords,
        "raw": metadata,
    }
