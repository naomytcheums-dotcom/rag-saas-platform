"""
Coverage audit -- unit tests for api/services/storage.py's error branches.
tests/test_avatar_storage_integration.py already covers the happy paths
and content-validation branches against a real S3-compatible bucket;
this file covers what that one can't cleanly simulate: S3 itself being
unreachable/erroring, and storage not being configured at all. No real
network needed here -- boto3 is mocked directly, same approach as
test_email_service.py's mocked httpx.post.

Partie 1.3.10's upload_organization_logo/upload_organization_favicon
add a REAL Pillow decode + pixel-dimension check on top of avatars'
existing magic-byte detection -- exercised here with actual generated
image bytes (io.BytesIO + PIL.Image, not hand-crafted hex blobs), since
that's genuinely what makes a dimension check meaningful to test.
"""

import io

from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image

from api.config import settings
from api.services import storage


def _png_bytes(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(255, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def _client_error(operation: str) -> ClientError:
    return ClientError({"Error": {"Code": "InternalError", "Message": "simulated S3 failure"}}, operation)


def test_client_raises_a_clear_error_when_s3_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", None)
    try:
        storage._client()
        assert False, "expected EnvironmentError"
    except EnvironmentError as exc:
        assert "S3_BUCKET_NAME" in str(exc)


def test_upload_avatar_wraps_a_client_error_from_s3(monkeypatch):
    """The real external-service-failure path: put_object itself fails
    (bucket permissions, S3 outage, etc.) -- upload_avatar must turn
    this into a RuntimeError the router translates to a 502, not let a
    raw botocore exception escape to the caller."""
    class _FailingClient:
        def put_object(self, **kwargs):
            raise _client_error("PutObject")

    monkeypatch.setattr(storage, "_client", lambda: _FailingClient())

    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c626001000000050001a5f645400000000049454e44ae426082"
    )
    try:
        storage.upload_avatar("user-id-irrelevant-here", png_bytes)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "avatar upload failed" in str(exc)


def test_upload_avatar_wraps_a_botocore_error_from_s3(monkeypatch):
    class _FailingClient:
        def put_object(self, **kwargs):
            raise BotoCoreError()

    monkeypatch.setattr(storage, "_client", lambda: _FailingClient())

    try:
        storage.upload_avatar("user-id-irrelevant-here", b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


def test_delete_avatar_is_a_no_op_when_s3_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", None)
    storage.delete_avatar("https://example.com/avatars/some-key.png")  # must not raise


def test_delete_avatar_is_a_no_op_for_a_url_that_does_not_look_like_ours(monkeypatch):
    """avatar_url is just a string column on User -- nothing stops it
    from being unset/malformed on an old row. Must not raise or attempt
    a delete against a URL from a completely different bucket/host."""
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "avatars")
    called = []
    monkeypatch.setattr(storage, "_client", lambda: called.append("should not be reached"))

    storage.delete_avatar("https://totally-unrelated.example.com/nothing/here.png")

    assert called == []


def test_delete_avatar_silently_swallows_a_client_error(monkeypatch):
    """Best-effort cleanup during api/tasks/account_purge.py's sweep --
    a storage hiccup on the cleanup half of the job must not fail/retry
    the whole purge, which already hard-deleted the database row."""
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "avatars")

    class _FailingClient:
        def delete_object(self, **kwargs):
            raise _client_error("DeleteObject")

    monkeypatch.setattr(storage, "_client", lambda: _FailingClient())

    storage.delete_avatar("https://example.com/avatars/some-user/some-key.png")  # must not raise


# ---------------------------------------------- Partie 1.3.10 -- branding --

def test_upload_organization_logo_rejects_oversized_file():
    oversized = b"\x00" * (storage.MAX_LOGO_BYTES + 1)
    try:
        storage.upload_organization_logo("org-id-irrelevant", oversized)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "exceeds" in str(exc)


def test_upload_organization_favicon_rejects_oversized_file():
    oversized = b"\x00" * (storage.MAX_FAVICON_BYTES + 1)
    try:
        storage.upload_organization_favicon("org-id-irrelevant", oversized)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "exceeds" in str(exc)


def test_upload_organization_logo_rejects_a_non_image_content_type():
    try:
        storage.upload_organization_logo("org-id-irrelevant", b"this is not actually an image")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "not a recognized image" in str(exc)


def test_upload_organization_logo_rejects_undecodable_bytes_despite_valid_magic_number():
    """The magic-byte signature alone isn't trusted -- a file that
    matches a PNG's leading bytes but Pillow itself can't decode
    (truncated, corrupted, or a signature-spoofing attempt) is rejected
    too, not just a file with the wrong signature entirely."""
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20  # valid signature, garbage body
    try:
        storage.upload_organization_logo("org-id-irrelevant", fake_png)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "could not be decoded" in str(exc)


def test_upload_organization_logo_rejects_oversized_dimensions():
    oversized_image = _png_bytes(storage.MAX_LOGO_DIMENSION_PX + 1, 10)
    try:
        storage.upload_organization_logo("org-id-irrelevant", oversized_image)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "dimensions" in str(exc)


def test_upload_organization_favicon_rejects_oversized_dimensions():
    """Favicon's dimension limit is much smaller than logo's -- an image
    that would be perfectly acceptable as a logo must still be rejected
    here."""
    too_big_for_a_favicon = _png_bytes(storage.MAX_FAVICON_DIMENSION_PX + 1, storage.MAX_FAVICON_DIMENSION_PX + 1)
    try:
        storage.upload_organization_favicon("org-id-irrelevant", too_big_for_a_favicon)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "dimensions" in str(exc)


def test_upload_organization_logo_succeeds_with_a_valid_small_image(monkeypatch):
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "avatars")
    monkeypatch.setattr(settings, "S3_PUBLIC_BASE_URL", "https://cdn.example.com/public/avatars")

    captured = {}

    class _FakeClient:
        def put_object(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(storage, "_client", lambda: _FakeClient())

    url = storage.upload_organization_logo("11111111-1111-1111-1111-111111111111", _png_bytes(64, 64))

    assert captured["Bucket"] == "avatars"
    assert captured["Key"].startswith("branding/11111111-1111-1111-1111-111111111111/logo-")
    assert url.startswith("https://cdn.example.com/public/avatars/branding/")


def test_upload_organization_logo_wraps_a_client_error_from_s3(monkeypatch):
    class _FailingClient:
        def put_object(self, **kwargs):
            raise _client_error("PutObject")

    monkeypatch.setattr(storage, "_client", lambda: _FailingClient())

    try:
        storage.upload_organization_logo("org-id-irrelevant", _png_bytes(32, 32))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "logo upload failed" in str(exc)


def test_delete_branding_asset_is_a_no_op_for_a_url_that_does_not_look_like_ours(monkeypatch):
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "avatars")
    called = []
    monkeypatch.setattr(storage, "_client", lambda: called.append("should not be reached"))

    storage.delete_branding_asset("https://totally-unrelated.example.com/nothing/here.png")

    assert called == []


def test_delete_branding_asset_silently_swallows_a_client_error(monkeypatch):
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "avatars")

    class _FailingClient:
        def delete_object(self, **kwargs):
            raise _client_error("DeleteObject")

    monkeypatch.setattr(storage, "_client", lambda: _FailingClient())

    storage.delete_branding_asset("https://example.com/avatars/branding/some-org/logo-key.png")  # must not raise
