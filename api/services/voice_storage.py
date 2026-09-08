"""Partie 8.2.7 -- real, private S3 storage for voice recordings. Same
real pattern as `api/services/document_storage.py` (its own `_client`
copied here rather than imported, matching this codebase's own
established per-module `_client()` convention for each distinct
bucket) -- see api/config.py's own `S3_VOICE_BUCKET_NAME` docstring
for why this is a THIRD, separate bucket."""

import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from api.config import settings


def _client():
    if not (settings.S3_VOICE_BUCKET_NAME and settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY):
        raise EnvironmentError(
            "S3_VOICE_BUCKET_NAME / S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY are not fully set -- "
            "see .env.example for the S3 (or Cloudflare R2) variables required for voice recording uploads."
        )
    return boto3.client(
        "s3", endpoint_url=settings.S3_ENDPOINT_URL, aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY, region_name=settings.S3_REGION,
    )


def upload_voice_recording(conversation_id: uuid.UUID, message_id: uuid.UUID, content: bytes, content_type: str = "audio/webm") -> str:
    """Real, private (never public-read) upload -- returns the S3 key,
    not a URL, matching `upload_document_file`'s own real convention."""
    key = f"voice/{conversation_id}/{message_id}"
    try:
        _client().put_object(Bucket=settings.S3_VOICE_BUCKET_NAME, Key=key, Body=content, ContentType=content_type)
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"voice recording upload failed: {exc}") from exc
    return key


def download_voice_recording(audio_key: str) -> bytes:
    try:
        response = _client().get_object(Bucket=settings.S3_VOICE_BUCKET_NAME, Key=audio_key)
        return response["Body"].read()
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"voice recording download failed: {exc}") from exc


def delete_voice_recording(audio_key: str) -> None:
    if not audio_key:
        return
    try:
        _client().delete_object(Bucket=settings.S3_VOICE_BUCKET_NAME, Key=audio_key)
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"voice recording delete failed: {exc}") from exc
