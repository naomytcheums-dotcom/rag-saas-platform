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


def _detect_image_content_type(content: bytes) -> str | None:
    """
    Identifies the real image format from the file's own leading magic
    bytes, independent of whatever Content-Type header the client
    declared. A client can put any string in that header (it's just a
    form field), but can't fake these signature bytes without producing
    a file that genuinely isn't a valid image of that type -- this is
    what upload_avatar() below actually trusts, not the declared header.
    Returns None if the content doesn't match any allowed signature.
    """
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    # WEBP: a RIFF container ("RIFF" + 4-byte size) whose form type is "WEBP"
    if len(content) >= 12 and content[0:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


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


def upload_avatar(user_id: uuid.UUID, content: bytes) -> str:
    """
    Validates and uploads one avatar image, returning its public URL.
    Called by api/routers/account.py's upload_avatar_route(), which
    handles the HTTP side (reading the uploaded file, catching the
    exceptions this function raises and turning them into the right
    status code) -- this function itself has no FastAPI/HTTP awareness.

    Takes no content_type parameter on purpose: the declared
    Content-Type from the upload is never trusted for validation, only
    what _detect_image_content_type() above reads from the file's own
    bytes is. A file that isn't actually a PNG/JPEG/WEBP is rejected
    here regardless of what header claimed otherwise.
    """
    if len(content) > MAX_AVATAR_BYTES:
        raise ValueError(f"avatar exceeds the {MAX_AVATAR_BYTES // (1024 * 1024)}MB limit")

    content_type = _detect_image_content_type(content)
    if content_type is None:
        raise ValueError(f"file is not a recognized image (PNG/JPEG/WEBP checked by its actual content, not the declared type) -- allowed: {sorted(ALLOWED_AVATAR_CONTENT_TYPES)}")

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


def delete_avatar(avatar_url: str) -> None:
    """
    Removes one avatar object from the bucket given its public URL (the
    same string stored in User.avatar_url). Used by
    api/tasks/account_purge.py so a hard-deleted account doesn't leave
    its avatar orphaned in storage forever. Silently does nothing for a
    URL that doesn't look like one of ours (defensive -- avatar_url is
    just a string column, nothing stops it from being unset/malformed on
    an old row) rather than raising and blocking the rest of the purge.
    """
    if not (settings.S3_BUCKET_NAME and avatar_url):
        return
    marker = f"/{settings.S3_BUCKET_NAME}/"
    if marker not in avatar_url:
        return
    key = avatar_url.split(marker, 1)[1]

    try:
        _client().delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
    except (BotoCoreError, ClientError):
        # Best-effort: a purge that already deleted the database row
        # shouldn't fail/retry the whole task over a storage hiccup on
        # the cleanup half of the job -- see account_purge.py's caller.
        pass
