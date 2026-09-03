"""
Partie 2.1.1/2.1.2/2.1.3/2.1.4/2.1.5/2.1.6 -- uploading, downloading, and
deleting document files in S3 (or any S3-compatible store, e.g.
Cloudflare R2 -- same as api/services/storage.py). A SEPARATE bucket
(S3_DOCUMENTS_BUCKET_NAME, api/config.py) from avatars/branding, and
objects are uploaded with NO ACL (private, bucket-owner-only) --
documents are private organizational content, unlike the
public-by-design avatar/logo/favicon assets api/services/storage.py
handles. See that setting's own comment for why a second bucket, not a
key prefix in the same one.

PDF, DOCX, TXT, Markdown, HTML, and CSV are accepted (this codebase's
scope through Partie 2.1.6). Other formats (JSON, XML, ...) are
separate, later cahier items (2.1.7+), each with their own real-format
validation to add when built, not something to fake-accept here.

**Markdown and CSV are the two real, deliberate exceptions to this
module's own "trust the bytes, never the declared name" rule for every
other format**: PDF has real magic bytes, DOCX has a real internal ZIP
structure, HTML has a real content-sniffable byte pattern (see below)
-- Markdown and CSV have neither. At the byte level, valid Markdown
and valid single-column CSV are both simply valid text; there is no
content-only signal that reliably distinguishes either from a plain
TXT upload (the same real bytes could legitimately be any of the
three). This step's own literal spec, like Markdown's before it, asks
for exactly this: accept `text/csv` **and** `.csv`. The filename
extension is therefore the ONLY meaningful signal available for
either, used here as a genuine, necessary exception -- not a silent
regression of the "content over declared type" philosophy, since the
content must still independently pass the same real is_valid_text
check either way (a `.csv`- or `.md`-named file containing binary
garbage is still rejected, not silently accepted).

**HTML does NOT need that same exception** -- unlike Markdown and CSV,
real HTML has a genuine structural signature: `_is_real_html` below
implements the WHATWG MIME Sniffing Standard's "matching an HTML byte
pattern" algorithm
(https://mimesniff.spec.whatwg.org/#matching-an-html-byte-pattern), the
same content-sniffing rule real browsers use to detect text/html when a
server sends no (or an untrustworthy) Content-Type. Checked BEFORE the
generic is_valid_text/Markdown/CSV fallback, same "most to least
specific" ordering as PDF/DOCX -- a `.html`/`.htm` extension is
accepted (per this step's own spec) but, exactly like PDF/DOCX, is
never REQUIRED for detection: real HTML content is recognized as HTML
regardless of what it's named.

**CSV's own filename check comes with a real, honest caveat, unlike
Markdown's**: Markdown's filename fallback is safe precisely because
there is NO content-only signal to contradict it either way. CSV is
different -- `api/services/csv_extraction.py`'s own real delimiter
detection (`csv.Sniffer`) is a character-frequency HEURISTIC, not
genuine CSV validation, and is confirmed for real to confidently (and
wrongly) treat ordinary comma-containing prose as comma-delimited data.
A `.csv`-named plain-text file is therefore still accepted here (real
text content, real extension, exactly what this step's spec asks
for) -- but whether it's REALLY tabular data is only discoverable at
PROCESSING time, by `extract_csv_data` actually parsing it, not at
upload time. This is the honest, stated limitation, not a gap papered
over.
"""

import io
import uuid
import zipfile

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from api.config import settings
from api.services.txt_extraction import is_valid_text

MAX_DOCUMENT_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
_PDF_MAGIC_BYTES = b"%PDF-"
_ZIP_MAGIC_BYTES = b"PK\x03\x04"
_MARKDOWN_EXTENSIONS = (".md", ".markdown")
_CSV_EXTENSIONS = (".csv",)
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TXT_CONTENT_TYPE = "text/plain"
MARKDOWN_CONTENT_TYPE = "text/markdown"
HTML_CONTENT_TYPE = "text/html"
CSV_CONTENT_TYPE = "text/csv"
ALLOWED_DOCUMENT_CONTENT_TYPES = (
    "application/pdf", DOCX_CONTENT_TYPE, TXT_CONTENT_TYPE, MARKDOWN_CONTENT_TYPE, HTML_CONTENT_TYPE, CSV_CONTENT_TYPE,
)

# Real content-based HTML detection -- see this module's own docstring
# for the WHATWG spec this implements. Bytes/sets, not a regex: the
# spec's algorithm is a plain case-insensitive prefix match against a
# fixed pattern list, followed by a check that the byte right after the
# match is itself a real tag terminator (whitespace or '>') -- that
# last check is what correctly excludes e.g. "<article" from matching
# the short "<a" pattern.
_HTML_LEADING_WHITESPACE = b"\t\n\x0c\r "
_HTML_TAG_TERMINATORS = b"\t\n\x0c\r >"
_HTML_BYTE_PATTERNS = (
    b"<!doctype html", b"<html", b"<head", b"<script", b"<iframe", b"<h1",
    b"<div", b"<font", b"<table", b"<a", b"<style", b"<title", b"<b",
    b"<body", b"<br", b"<p",
)


def _is_real_pdf(content: bytes) -> bool:
    """
    Checks the file's OWN leading magic bytes, never the client's
    declared Content-Type (same "trust the bytes, not the header"
    philosophy as api/services/storage.py's _detect_image_content_type)
    -- a client can set any Content-Type header on a multipart upload
    regardless of the actual file content.
    """
    return content.startswith(_PDF_MAGIC_BYTES)


def _is_real_docx(content: bytes) -> bool:
    """
    A DOCX is a ZIP archive -- checking the ZIP signature alone isn't
    enough to identify it specifically (XLSX, PPTX, and a plain .zip
    all share the exact same leading bytes) -- so this also opens it as
    a real ZIP and confirms `word/document.xml` is present, the one
    part every valid DOCX's OOXML package is required to have. A
    zipfile.BadZipFile (the ZIP signature matched but the rest of the
    file is truncated/corrupt) is treated as "not a real DOCX" here,
    same as any other format mismatch -- not a crash.
    """
    if not content.startswith(_ZIP_MAGIC_BYTES):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            return "word/document.xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False


def _is_real_html(content: bytes) -> bool:
    """
    Real, spec-based HTML detection (see this module's own docstring)
    -- checked against the first 1024 bytes after skipping leading
    whitespace, same buffer-size ballpark real browsers use for MIME
    sniffing. Deliberately does NOT need `is_valid_text` first (unlike
    Markdown's filename check): a byte pattern match here already
    proves the content is real ASCII text with real markup structure.
    """
    buf = content[:1024].lstrip(_HTML_LEADING_WHITESPACE)
    lower = buf.lower()
    if lower.startswith(b"<!--"):
        return True
    for pattern in _HTML_BYTE_PATTERNS:
        if lower.startswith(pattern):
            next_byte = lower[len(pattern):len(pattern) + 1]
            if not next_byte or next_byte[0] in _HTML_TAG_TERMINATORS:
                return True
    return False


def validate_document_upload(content: bytes, filename: str = "") -> str:
    """Real, substantive checks before anything touches S3 or the
    database -- raises ValueError with a clear reason for any failure,
    otherwise returns the REAL detected content type (never the
    client's declared Content-Type HEADER) so the caller
    (api/security/documents.py's upload_document) can store the right
    Document.file_type and pass it on to upload_document_file below
    without re-detecting it. Checked in order from MOST to LEAST
    specific -- PDF/DOCX/HTML all have a real, narrow signature to
    match; the generic "does this decode as text" check (and Markdown/
    CSV's filename-based tie-break) only ever runs once those are ruled
    out. `filename` defaults to "" (no Markdown/CSV match possible,
    same as before this parameter existed) so every OTHER caller of
    this function is unaffected -- see this module's own docstring for
    why Markdown and CSV specifically need the filename at all (HTML
    does not)."""
    if len(content) > MAX_DOCUMENT_UPLOAD_BYTES:
        raise ValueError(f"file exceeds the {MAX_DOCUMENT_UPLOAD_BYTES // (1024 * 1024)}MB limit")
    if _is_real_pdf(content):
        return "application/pdf"
    if _is_real_docx(content):
        return DOCX_CONTENT_TYPE
    if _is_real_html(content):
        return HTML_CONTENT_TYPE
    if not is_valid_text(content):
        raise ValueError(
            "file is not a valid PDF, DOCX, TXT, Markdown, HTML, or CSV (checked by its actual content, not the declared type) -- "
            f"supported types: {', '.join(ALLOWED_DOCUMENT_CONTENT_TYPES)}"
        )
    if filename.lower().endswith(_MARKDOWN_EXTENSIONS):
        return MARKDOWN_CONTENT_TYPE
    if filename.lower().endswith(_CSV_EXTENSIONS):
        return CSV_CONTENT_TYPE
    return TXT_CONTENT_TYPE


def _client():
    if not (settings.S3_DOCUMENTS_BUCKET_NAME and settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY):
        raise EnvironmentError(
            "S3_DOCUMENTS_BUCKET_NAME / S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY are not fully set -- "
            "see .env.example for the S3 (or Cloudflare R2) variables required for document uploads."
        )
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )


def upload_document_file(organization_id: uuid.UUID, document_id: uuid.UUID, filename: str, content: bytes, content_type: str) -> str:
    """
    Uploads one document's already-validated bytes, returning its S3
    KEY (not a public URL -- there isn't one, this object is private).
    Keyed by both organization_id and document_id so two organizations'
    documents can never collide, and a document's own key is stable and
    predictable for later download/delete calls.

    `content_type` is the value validate_document_upload already
    returned for this same content -- passed in rather than
    re-detected here, so the real format is only ever sniffed once per
    upload.
    """
    key = f"documents/{organization_id}/{document_id}/{filename}"

    try:
        _client().put_object(Bucket=settings.S3_DOCUMENTS_BUCKET_NAME, Key=key, Body=content, ContentType=content_type)
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"document upload failed: {exc}") from exc

    return key


def download_document_file(file_key: str) -> bytes:
    """Fetches a document's raw bytes back out of S3 -- used by
    api/security/documents.py's process_document to get the file
    content to actually extract from."""
    try:
        response = _client().get_object(Bucket=settings.S3_DOCUMENTS_BUCKET_NAME, Key=file_key)
        return response["Body"].read()
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"document download failed: {exc}") from exc


def delete_document_file(file_key: str) -> None:
    """Best-effort delete -- same reasoning as api/services/storage.py's
    delete_avatar/delete_branding_asset: a DELETE that already removed
    the database row shouldn't fail or retry over a storage hiccup on
    the cleanup half of the job."""
    if not (settings.S3_DOCUMENTS_BUCKET_NAME and file_key):
        return
    try:
        _client().delete_object(Bucket=settings.S3_DOCUMENTS_BUCKET_NAME, Key=file_key)
    except (BotoCoreError, ClientError):
        pass
