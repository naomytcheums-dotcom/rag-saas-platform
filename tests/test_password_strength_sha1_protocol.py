import hashlib

from api.security import password_strength


async def test_hibp_hash_marks_sha1_as_non_security_use_and_preserves_prefix(
    monkeypatch,
):
    password = "correct-horse-battery-staple"
    original_sha1 = hashlib.sha1
    calls = []
    requested_urls = []

    def recording_sha1(data, **kwargs):
        calls.append(kwargs)
        return original_sha1(data, **kwargs)

    class Response:
        text = ""

        def raise_for_status(self):
            pass

    class Client:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            requested_urls.append((url, headers))
            return Response()

    monkeypatch.setattr(password_strength.hashlib, "sha1", recording_sha1)
    monkeypatch.setattr(password_strength.httpx, "AsyncClient", Client)

    assert await password_strength.is_password_known_breached(password) is False

    expected_prefix = (
        original_sha1(password.encode("utf-8"), usedforsecurity=False)
        .hexdigest()
        .upper()[:5]
    )
    assert calls == [{"usedforsecurity": False}]
    assert requested_urls == [
        (
            f"{password_strength._HIBP_RANGE_URL}{expected_prefix}",
            {"Add-Padding": "true"},
        )
    ]
