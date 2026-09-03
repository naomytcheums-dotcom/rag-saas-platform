"""
Partie 2.1.1/2.1.2/2.1.3 -- uploading, downloading, and deleting
document files in S3 (or any S3-compatible store, e.g. Cloudflare R2 --
same as api/services/storage.py). A SEPARATE bucket
(S3_DOCUMENTS_BUCKET_NAME, api/config.py) from avatars/branding, and
objects are uploaded with NO ACL (private, bucket-owner-only) --
documents are private organizational content, unlike the
public-by-design avatar/logo/favicon assets api/services/storage.py
handles. See that setting's own comment for why a second bucket, not a
key prefix in the same one.

PDF, DOCX, and TXT are accepted (this codebase's scope through Partie
2.1.3). Other formats (HTML, CSV, ...) are separate, later cahier items
(2.1.4+), each with their own real-format validation to add when built,
not something to fake-accept here.
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
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TXT_CONTENT_TYPE = "text/plain"
ALLOWED_DOCUMENT_CONTENT_TYPES = ("application/pdf", DOCX_CONTENT_TYPE, TXT_CONTENT_TYPE)


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


def validate_document_upload(content: bytes) -> str:
    """Real, substantive checks before anything touches S3 or the
    database -- raises ValueError with a clear reason for any failure,
    otherwise returns the REAL detected content type (never the
    client's declared one) so the caller (api/security/documents.py's
    upload_document) can store the right Document.file_type and pass it
    on to upload_document_file below without re-detecting it. Checked in
    order from MOST to LEAST specific -- PDF/DOCX both have a real,
    narrow signature to match; a generic "does this decode as text"
    check could otherwise misclassify almost anything, so it only ever
    runs as the last, catch-all check once the more specific formats
    have already been ruled out."""
    if len(content) > MAX_DOCUMENT_UPLOAD_BYTES:
        raise ValueError(f"file exceeds the {MAX_DOCUMENT_UPLOAD_BYTES // (1024 * 1024)}MB limit")
    if _is_real_pdf(content):
        return "application/pdf"
    if _is_real_docx(content):
        return DOCX_CONTENT_TYPE
    if is_valid_text(content):
        return TXT_CONTENT_TYPE
    raise ValueError(
        "file is not a valid PDF, DOCX, or TXT (checked by its actual content, not the declared type) -- "
        f"supported types: {', '.join(ALLOWED_DOCUMENT_CONTENT_TYPES)}"
    )


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
