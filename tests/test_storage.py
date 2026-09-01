"""
Coverage audit -- unit tests for api/services/storage.py's error branches.
tests/test_avatar_storage_integration.py already covers the happy paths
and content-validation branches against a real S3-compatible bucket;
this file covers what that one can't cleanly simulate: S3 itself being
unreachable/erroring, and storage not being configured at all. No real
network needed here -- boto3 is mocked directly, same approach as
test_email_service.py's mocked httpx.post.
"""

from botocore.exceptions import BotoCoreError, ClientError

from api.config import settings
from api.services import storage


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
