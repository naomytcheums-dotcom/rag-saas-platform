"""
Avatar upload (1.1.13) to any S3-compatible bucket -- real AWS S3 (leave
S3_ENDPOINT_URL unset) or Cloudflare R2 (set it to your account's R2
endpoint). boto3 talks to both identically since R2 implements the S3 API.
"""

import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from api.config import settings

MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_AVATAR_CONTENT_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def _client():
    """Builds a fresh boto3 S3 client from whatever S3_* settings are
    configured -- a new one per call rather than a cached singleton,
    since avatar uploads are infrequent enough that the connection-setup
    cost doesn't matter, and it keeps this module free of global state."""
    if not (settings.S3_BUCKET_NAME and settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY):
        raise EnvironmentError(
            "S3_BUCKET_NAME / S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY are not fully set -- "
            "see .env.example for the S3 (or Cloudflare R2) variables required for avatar uploads."
        )
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,  # None -> real AWS S3
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )


def upload_avatar(user_id: uuid.UUID, content: bytes, content_type: str) -> str:
    """
    Validates and uploads one avatar image, returning its public URL.
    Called by api/routers/account.py's upload_avatar_route(), which
    handles the HTTP side (reading the uploaded file, catching the
    exceptions this function raises and turning them into the right
    status code) -- this function itself has no FastAPI/HTTP awareness.

    content_type is trusted from what the browser/client declared, not
    verified against the file's actual magic bytes -- a known,
    documented gap for a future hardening pass (see AUDIT.md's spirit:
    the RAG pipeline's own audit already flags "validate magic bytes,
    not just declared MIME type" as a real class of issue).
    """
    if content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
        raise ValueError(f"unsupported avatar content type '{content_type}' -- allowed: {sorted(ALLOWED_AVATAR_CONTENT_TYPES)}")
    if len(content) > MAX_AVATAR_BYTES:
        raise ValueError(f"avatar exceeds the {MAX_AVATAR_BYTES // (1024 * 1024)}MB limit")

    extension = ALLOWED_AVATAR_CONTENT_TYPES[content_type]
    # No "avatars/" prefix here: S3_BUCKET_NAME is expected to be a bucket
    # dedicated to avatars (that's what .env.example documents), so the
    # bucket name already provides that namespacing -- prefixing the key
    # too would duplicate it in S3_PUBLIC_BASE_URL (.../public/avatars/avatars/...).
    # A fresh random key per upload (not user_id.png) so old CDN/browser
    # caches never serve a stale avatar under the same URL.
    key = f"{user_id}/{uuid.uuid4()}.{extension}"

    try:
        _client().put_object(
            Bucket=settings.S3_BUCKET_NAME, Key=key, Body=content, ContentType=content_type, ACL="public-read"
        )
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"avatar upload failed: {exc}") from exc

    base = settings.S3_PUBLIC_BASE_URL or f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET_NAME}"
    return f"{base.rstrip('/')}/{key}"
