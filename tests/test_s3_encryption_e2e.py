"""Spec 10.1.14: uploaded files are encrypted at rest by the object store, proved on the store's own disk.

A throw-away MinIO container is started with a KMS key (MINIO_KMS_SECRET_KEY, what makes SSE-S3 available in MinIO). The application's real upload functions
(`upload_document_file`, `upload_voice_recording`) write a file holding a unique marker:

  * with S3_SERVER_SIDE_ENCRYPTION unset (negative control) the marker is readable in the store's data directory: the test would notice a store that does not encrypt;
  * with S3_SERVER_SIDE_ENCRYPTION=AES256 the store reports `ServerSideEncryption: AES256` for the object, the marker appears nowhere in its data directory, and the
    application still downloads the original bytes (decryption is transparent);
  * an invalid mode is refused at startup; aws:kms forwards the key id (unit level: a real KMS needs an AWS account, see docs/security/ENCRYPTION_AT_REST.md).

Needs Docker and the MinIO image already present (the one CI uses) or pullable; skipped otherwise. Ports are allocated by Docker (never a fixed one)."""

import base64
import os
import shutil
import subprocess
import time
import uuid

import boto3
import pytest

from api.config import Settings, settings
from api.services import document_storage, voice_storage
from api.services.s3_encryption import object_encryption_args, verify_object_encrypted

IMAGE = os.environ.get("MINIO_TEST_IMAGE", "bitnamilegacy/minio:2025.7.23-debian-12-r5")
MARKER = "AT-REST-MARKER-5d1e9c77-must-not-appear-on-disk"
pytestmark = pytest.mark.skipif(not shutil.which("docker"), reason="needs Docker")


def _docker(*args, check=True):
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=check, env=dict(os.environ, MSYS_NO_PATHCONV="1"))


@pytest.fixture(scope="module")
def minio():
    if _docker("image", "inspect", IMAGE, check=False).returncode != 0:
        pytest.skip(f"{IMAGE} is not present locally (set MINIO_TEST_IMAGE)")
    name = f"rag-test-sse-{uuid.uuid4().hex[:8]}"
    kms = "test-key:" + base64.b64encode(os.urandom(32)).decode()
    _docker("run", "-d", "--name", name, "-p", "127.0.0.1::9000", "-e", "MINIO_ROOT_USER=ssetestuser", "-e", "MINIO_ROOT_PASSWORD=ssetestpassword1", "-e", f"MINIO_KMS_SECRET_KEY={kms}", IMAGE)
    try:
        port = _docker("port", name, "9000/tcp").stdout.strip().splitlines()[0].rsplit(":", 1)[1]
        endpoint = f"http://127.0.0.1:{port}"
        client = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id="ssetestuser", aws_secret_access_key="ssetestpassword1", region_name="us-east-1")
        for _ in range(60):
            try:
                client.list_buckets()
                break
            except Exception:  # noqa: BLE001 -- the server is still starting
                time.sleep(1)
        else:
            pytest.fail("the disposable MinIO did not start: " + _docker("logs", name, check=False).stdout[-500:])
        for bucket in ("documents", "voice"):
            client.create_bucket(Bucket=bucket)
        yield {"name": name, "endpoint": endpoint, "client": client}
    finally:
        _docker("rm", "-f", "-v", name, check=False)


@pytest.fixture
def storage(minio, monkeypatch):
    for attr, value in {
        "S3_ENDPOINT_URL": minio["endpoint"], "S3_ACCESS_KEY_ID": "ssetestuser", "S3_SECRET_ACCESS_KEY": "ssetestpassword1", "S3_REGION": "us-east-1",
        "S3_DOCUMENTS_BUCKET_NAME": "documents", "S3_VOICE_BUCKET_NAME": "voice",
    }.items():
        monkeypatch.setattr(settings, attr, value)
    return minio


def _on_disk(minio, marker: str) -> int:
    """How many files of the store's data directory contain the marker."""
    found = _docker("exec", minio["name"], "sh", "-c", f"grep -rl --binary-files=text '{marker}' /bitnami/minio/data 2>/dev/null | wc -l")
    return int(found.stdout.strip() or 0)


def test_without_the_setting_the_marker_is_readable_on_the_stores_disk(storage, monkeypatch):
    """Negative control: proves the disk scan below is able to see a plaintext object."""
    monkeypatch.setattr(settings, "S3_SERVER_SIDE_ENCRYPTION", None)
    marker = f"{MARKER}-plain-{uuid.uuid4().hex[:6]}"
    key = document_storage.upload_document_file(uuid.uuid4(), uuid.uuid4(), "plain.txt", marker.encode() * 20, "text/plain")
    head = storage["client"].head_object(Bucket="documents", Key=key)
    assert "ServerSideEncryption" not in head
    with pytest.raises(RuntimeError, match="without server-side encryption"):
        verify_object_encrypted(storage["client"], "documents", key)
    assert _on_disk(storage, marker) >= 1


def test_with_aes256_the_store_encrypts_and_the_application_still_reads_the_file(storage, monkeypatch):
    monkeypatch.setattr(settings, "S3_SERVER_SIDE_ENCRYPTION", "AES256")
    marker = f"{MARKER}-sse-{uuid.uuid4().hex[:6]}"
    content = (marker + " ").encode() * 50
    key = document_storage.upload_document_file(uuid.uuid4(), uuid.uuid4(), "secret.txt", content, "text/plain")
    assert verify_object_encrypted(storage["client"], "documents", key) == "AES256"
    assert _on_disk(storage, marker) == 0, "the plaintext is on the store's disk"
    assert document_storage.download_document_file(key) == content  # transparent decryption for the application

    voice_key = voice_storage.upload_voice_recording(uuid.uuid4(), uuid.uuid4(), marker.encode() * 30, "audio/webm")
    assert verify_object_encrypted(storage["client"], "voice", voice_key) == "AES256"
    assert _on_disk(storage, marker) == 0


def test_the_arguments_forwarded_to_the_store(monkeypatch):
    monkeypatch.setattr(settings, "S3_SERVER_SIDE_ENCRYPTION", None)
    assert object_encryption_args() == {}
    monkeypatch.setattr(settings, "S3_SERVER_SIDE_ENCRYPTION", "")
    assert object_encryption_args() == {}
    monkeypatch.setattr(settings, "S3_SERVER_SIDE_ENCRYPTION", "AES256")
    assert object_encryption_args() == {"ServerSideEncryption": "AES256"}
    monkeypatch.setattr(settings, "S3_SERVER_SIDE_ENCRYPTION", "aws:kms")
    monkeypatch.setattr(settings, "S3_SSE_KMS_KEY_ID", "alias/rag-saas")
    assert object_encryption_args() == {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": "alias/rag-saas"}
    monkeypatch.setattr(settings, "S3_SERVER_SIDE_ENCRYPTION", "rot13")
    with pytest.raises(ValueError, match="S3_SERVER_SIDE_ENCRYPTION"):
        object_encryption_args()


def test_an_invalid_mode_is_refused_at_startup(monkeypatch):
    monkeypatch.setenv("S3_SERVER_SIDE_ENCRYPTION", "rot13")
    with pytest.raises(Exception, match="S3_SERVER_SIDE_ENCRYPTION"):
        Settings()
