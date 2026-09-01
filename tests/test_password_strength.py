"""
1.1-audit finding: unit tests for api/security/password_strength.py's
is_password_known_breached -- a real HTTP call to Have I Been Pwned's
k-anonymity API, stubbed out here with a fake httpx.AsyncClient.get so
these stay fast/offline like every other unit test in this file's
neighborhood (test_auth_security.py, test_email_service.py).
"""

import hashlib

import httpx
import pytest

from api.security import password_strength


class _FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", password_strength._HIBP_RANGE_URL)
            raise httpx.HTTPStatusError("error", request=request, response=httpx.Response(self.status_code, request=request))


class _FakeAsyncClient:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.requested_urls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, headers=None):
        self.requested_urls.append(url)
        if self._exc is not None:
            raise self._exc
        return self._response


def _suffix_for(password: str) -> str:
    return hashlib.sha1(password.encode("utf-8")).hexdigest().upper()[5:]


async def test_password_found_in_the_range_response_is_reported_as_breached(monkeypatch):
    password = "password123"
    suffix = _suffix_for(password)
    fake_client = _FakeAsyncClient(response=_FakeResponse(f"{suffix}:3730471\nAAAA0000AAAA0000AAAA0000AAAA0000AAA:1\n"))
    monkeypatch.setattr(password_strength.httpx, "AsyncClient", lambda timeout: fake_client)

    assert await password_strength.is_password_known_breached(password) is True


async def test_password_not_in_the_range_response_is_not_breached(monkeypatch):
    password = "a-genuinely-unique-passphrase-nobody-else-uses"
    fake_client = _FakeAsyncClient(response=_FakeResponse("AAAA0000AAAA0000AAAA0000AAAA0000AAA:1\n"))
    monkeypatch.setattr(password_strength.httpx, "AsyncClient", lambda timeout: fake_client)

    assert await password_strength.is_password_known_breached(password) is False


async def test_only_the_five_character_prefix_ever_leaves_this_process(monkeypatch):
    """The whole privacy point of k-anonymity mode -- proven here by
    inspecting the actual URL requested, not just trusting the
    docstring's claim."""
    password = "correct-horse-battery-staple"
    full_sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    fake_client = _FakeAsyncClient(response=_FakeResponse(f"{full_sha1[5:]}:1\n"))
    monkeypatch.setattr(password_strength.httpx, "AsyncClient", lambda timeout: fake_client)

    await password_strength.is_password_known_breached(password)

    assert len(fake_client.requested_urls) == 1
    requested = fake_client.requested_urls[0]
    assert requested.endswith(full_sha1[:5])
    assert full_sha1[5:] not in requested  # the suffix (and thus the full hash) never appears in the request


async def test_fails_open_on_a_network_error(monkeypatch):
    fake_client = _FakeAsyncClient(exc=httpx.ConnectError("connection refused"))
    monkeypatch.setattr(password_strength.httpx, "AsyncClient", lambda timeout: fake_client)

    assert await password_strength.is_password_known_breached("anything") is False


async def test_fails_open_on_a_non_200_response(monkeypatch):
    fake_client = _FakeAsyncClient(response=_FakeResponse("", status_code=503))
    monkeypatch.setattr(password_strength.httpx, "AsyncClient", lambda timeout: fake_client)

    assert await password_strength.is_password_known_breached("anything") is False


async def test_fails_open_on_a_timeout(monkeypatch):
    fake_client = _FakeAsyncClient(exc=httpx.TimeoutException("timed out"))
    monkeypatch.setattr(password_strength.httpx, "AsyncClient", lambda timeout: fake_client)

    assert await password_strength.is_password_known_breached("anything") is False
