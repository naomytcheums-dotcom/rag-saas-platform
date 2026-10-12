"""E2E finding 2026-10-12: a renamed GitHub repository answers 301; the importer must follow it inside GitHub only."""

import httpx
import pytest

from api.services import github_extraction as gh


def test_the_real_client_follows_a_few_redirects():
    client = gh._client()
    assert client.follow_redirects is True and client.max_redirects == 3


@pytest.mark.parametrize("url", ["https://api.github.com/repositories/160919119", "https://github.com/x", "https://raw.githubusercontent.com/a/b/c", "https://codeload.github.com/a/b/zip/main"])
async def test_github_hosts_are_allowed(url):
    await gh._refuse_request_outside_github(httpx.Request("GET", url))


@pytest.mark.parametrize("url", ["http://169.254.169.254/latest/meta-data", "http://127.0.0.1:8000/admin", "https://evil.example.com/x", "https://github.com.evil.example/x"])
async def test_other_hosts_are_refused(url):
    with pytest.raises(httpx.RequestError):
        await gh._refuse_request_outside_github(httpx.Request("GET", url))
