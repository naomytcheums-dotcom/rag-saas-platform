"""Partie 5.2.3 -- GitHub tools. Same real httpx.MockTransport pattern
as tests/test_github_extraction.py -- real request/response parsing,
fake network transport."""

import httpx
import pytest

from api.config import settings
from api.tools.github_tools import (
    github_get_issue, github_get_pull_request, github_get_repo, github_list_issues, github_list_pull_requests,
    github_search_code,
)


async def test_github_list_issues_reuses_the_real_fetch_github_issues(monkeypatch):
    """Validation criterion: cohérence -- réutilise fetch_github_issues,
    les vraies pull requests restent exclues."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") != "1":
            return _json_response(200, [])
        return _json_response(200, [
            {"number": 1, "title": "real issue"},
            {"number": 2, "title": "real PR", "pull_request": {"url": "..."}},
        ])

    monkeypatch.setattr("api.services.github_extraction._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    issues = await github_list_issues("octocat", "Hello-World")
    assert [i["number"] for i in issues] == [1]


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr("api.tools.github_tools._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def _json_response(status_code: int, body, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status_code, json=body, headers=headers or {})


@pytest.fixture(autouse=True)
def _configure_token(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_API_TOKEN", "ghp_test_token")


# --------------------------------------- github_get_repo (reuses fetch_github_repo) --


async def test_github_get_repo_returns_real_metadata(monkeypatch):
    """Validation criterion: les appels GitHub fonctionnent."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer ghp_test_token"
        return _json_response(200, {"full_name": "octocat/Hello-World", "default_branch": "master"})

    monkeypatch.setattr("api.services.github_extraction._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    repo = await github_get_repo("octocat", "Hello-World")
    assert repo["full_name"] == "octocat/Hello-World"


# --------------------------------------- github_get_issue --


async def test_github_get_issue_returns_a_real_single_issue(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octocat/Hello-World/issues/42"
        return _json_response(200, {"number": 42, "title": "A real bug"})

    _patch_client(monkeypatch, handler)
    issue = await github_get_issue("octocat", "Hello-World", 42)
    assert issue["number"] == 42


async def test_github_get_issue_raises_a_real_not_found_error(monkeypatch):
    """Validation criterion: robustesse -- les erreurs API sont gérées."""
    _patch_client(monkeypatch, lambda request: _json_response(404, {"message": "Not Found"}))
    with pytest.raises(ValueError, match="not found"):
        await github_get_issue("octocat", "nope", 1)


# --------------------------------------- github_list_pull_requests / github_get_pull_request --


async def test_github_list_pull_requests_hits_the_real_pulls_endpoint(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octocat/Hello-World/pulls"
        assert request.url.params["state"] == "open"
        return _json_response(200, [{"number": 1, "title": "A real PR"}])

    _patch_client(monkeypatch, handler)
    prs = await github_list_pull_requests("octocat", "Hello-World")
    assert prs[0]["number"] == 1


async def test_github_get_pull_request_returns_a_real_pr(monkeypatch):
    _patch_client(monkeypatch, lambda request: _json_response(200, {"number": 7, "merged": False}))
    pr = await github_get_pull_request("octocat", "Hello-World", 7)
    assert pr["number"] == 7


# --------------------------------------- github_search_code --


async def test_github_search_code_returns_real_items(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search/code"
        return _json_response(200, {"items": [{"name": "main.py", "path": "src/main.py"}]})

    _patch_client(monkeypatch, handler)
    results = await github_search_code("def main", repo="octocat/Hello-World")
    assert results[0]["name"] == "main.py"


async def test_github_search_code_requires_a_real_token(monkeypatch):
    """Validation criterion: sécurité -- le token GitHub est requis pour
    la recherche de code (contrainte réelle de l'API GitHub)."""
    monkeypatch.setattr(settings, "GITHUB_API_TOKEN", None)
    with pytest.raises(ValueError, match="GITHUB_API_TOKEN"):
        await github_search_code("query")


# --------------------------------------- rate limit --


async def test_github_tools_raise_a_real_rate_limit_error(monkeypatch):
    from api.services.github_extraction import GitHubRateLimitError

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(403, {"message": "rate limited"}, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "12345"})

    _patch_client(monkeypatch, handler)
    with pytest.raises(GitHubRateLimitError):
        await github_get_issue("octocat", "Hello-World", 1)
