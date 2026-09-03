"""
Partie 2.1.1 -- uploading, downloading, and deleting document files in
S3 (or any S3-compatible store, e.g. Cloudflare R2 -- same as
api/services/storage.py). A SEPARATE bucket (S3_DOCUMENTS_BUCKET_NAME,
api/config.py) from avatars/branding, and objects are uploaded with NO
ACL (private, bucket-owner-only) -- documents are private organizational
content, unlike the public-by-design avatar/logo/favicon assets
api/services/storage.py handles. See that setting's own comment for why
a second bucket, not a key prefix in the same one.

Only PDF is accepted -- this étape's own scope (Partie 2.1.1). Other
formats (DOCX, TXT, HTML, ...) are separate, later cahier items
(2.1.2+), each with their own real-format validation to add when built,
not something to fake-accept here.
"""

import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from api.config import settings

MAX_DOCUMENT_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
_PDF_MAGIC_BYTES = b"%PDF-"


def _is_real_pdf(content: bytes) -> bool:
    """
    Checks the file's OWN leading magic bytes, never the client's
    declared Content-Type (same "trust the bytes, not the header"
    philosophy as api/services/storage.py's _detect_image_content_type)
    -- a client can set any Content-Type header on a multipart upload
    regardless of the actual file content.
    """
    return content.startswith(_PDF_MAGIC_BYTES)


def validate_document_upload(content: bytes) -> None:
    """Real, substantive checks before anything touches S3 or the
    database -- raises ValueError with a clear reason for either
    failure. Called by api/security/documents.py's upload_document
    before it does anything else."""
    if len(content) > MAX_DOCUMENT_UPLOAD_BYTES:
        raise ValueError(f"file exceeds the {MAX_DOCUMENT_UPLOAD_BYTES // (1024 * 1024)}MB limit")
    if not _is_real_pdf(content):
        raise ValueError("file is not a valid PDF (checked by its actual content, not the declared type) -- only PDF is supported by this step")


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


def upload_document_file(organization_id: uuid.UUID, document_id: uuid.UUID, filename: str, content: bytes) -> str:
    """
    Validates and uploads one document's PDF bytes, returning its S3
    KEY (not a public URL -- there isn't one, this object is private).
    Keyed by both organization_id and document_id so two organizations'
    documents can never collide, and a document's own key is stable and
    predictable for later download/delete calls.
    """
    validate_document_upload(content)
    key = f"documents/{organization_id}/{document_id}/{filename}"

    try:
        _client().put_object(Bucket=settings.S3_DOCUMENTS_BUCKET_NAME, Key=key, Body=content, ContentType="application/pdf")
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"document upload failed: {exc}") from exc

    return key


def download_document_file(file_key: str) -> bytes:
    """Fetches a document's raw bytes back out of S3 -- used by
    api/security/documents.py's process_pdf_document to get the file
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
