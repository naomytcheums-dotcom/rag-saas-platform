"""Server-side encryption of the objects stored in S3-compatible storage (spec 10.1.14, "encryption at rest" of the uploaded content).

The application encrypts the secrets it stores in the database itself (api/security/encryption.py, api/security/secret_encryption.py). The uploaded files (documents,
extracted images, voice recordings, fine-tuning datasets, plugin sources) are delivered to the object store, and their encryption at rest is the store's job: this
module asks it to do it, on every write to a PRIVATE bucket, through the standard S3 headers:

  S3_SERVER_SIDE_ENCRYPTION=AES256      SSE-S3: the store encrypts with keys it manages (AWS S3, MinIO with a KMS configured, Cloudflare R2 always does)
  S3_SERVER_SIDE_ENCRYPTION=aws:kms     SSE-KMS: with S3_SSE_KMS_KEY_ID (a key id / ARN / alias); the key policy is then the access control

Unset (the default) sends no header: the store's own default applies, which may or may not encrypt (AWS S3 has encrypted every new object since January 2023; a bare
MinIO does not). Public-read buckets (avatars, branding) are public by design and are not covered. Whether a given store really encrypted an object is checked by
`verify_object_encrypted`, used by tests/test_s3_encryption_e2e.py against a real MinIO."""

from typing import Any

from api.config import settings

ALLOWED = ("AES256", "aws:kms")


def object_encryption_args() -> dict[str, Any]:
    """Extra put_object() arguments that request server-side encryption; empty when the operator did not ask for it."""
    mode = (settings.S3_SERVER_SIDE_ENCRYPTION or "").strip()
    if not mode:
        return {}
    if mode not in ALLOWED:
        raise ValueError(f"S3_SERVER_SIDE_ENCRYPTION must be one of {ALLOWED}, got {mode!r}")
    args: dict[str, Any] = {"ServerSideEncryption": mode}
    if mode == "aws:kms" and settings.S3_SSE_KMS_KEY_ID:
        args["SSEKMSKeyId"] = settings.S3_SSE_KMS_KEY_ID
    return args


def verify_object_encrypted(client, bucket: str, key: str) -> str:
    """The encryption the store reports for an existing object (head_object); raises when it reports none."""
    reported = client.head_object(Bucket=bucket, Key=key).get("ServerSideEncryption")
    if not reported:
        raise RuntimeError(f"s3://{bucket}/{key} is stored without server-side encryption")
    return reported
