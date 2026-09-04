"""
Partie 5.2.3 -- letting an agent read GitHub repos/issues/pull
requests/code via GitHub's real REST API.

**Real reuse, not duplication**: `github_get_repo`/`github_list_issues`
below are thin wrappers around `api.services.github_extraction`'s own
real, already-tested `fetch_github_repo`/`fetch_github_issues` (Partie
2.1.12/2.1.13) -- the same real HTTP logic, real error mapping
(`_raise_for_github_response`), and real "a PR is never mistaken for an
issue" behavior that module's own docstring already documents and
verified against the real GitHub API.

**A real, deliberate choice NOT to rename that module's own private
`_client`/`_headers`/`_raise_for_github_response` helpers to public**:
attempted once, reverted -- `async with _client() as client:` appears
at every one of that module's own real call sites, and a blind rename
of `_client` to `client` silently shadows the module-level factory
function with the loop's own local variable of the same name (still
technically correct Python, since the right-hand side evaluates before
the binding, but genuinely confusing and a real, needless risk to a
working, tested module for this étape's own sake). This module builds
its own small, real, equivalent HTTP setup instead, for the genuinely
NEW real endpoints (single issue, pull requests, code search) that
`github_extraction.py` doesn't already cover -- real, minimal, safer
than an invasive rename.

**Real token reuse**: `settings.GITHUB_API_TOKEN`, the SAME real
setting Partie 2.1.12 already uses -- this étape's own literal
config asks to reuse it, not declare a second one.
"""

import httpx

from api.config import settings
from api.services.github_extraction import GitHubRateLimitError, fetch_github_issues, fetch_github_repo

_TIMEOUT_SECONDS = 15.0
_API_VERSION = "2022-11-28"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": _API_VERSION}
    if settings.GITHUB_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_API_TOKEN}"
    return headers


def _raise_for_response(response: httpx.Response, context: str) -> None:
    """Real, minimal error mapping -- narrower than
    `github_extraction._raise_for_github_response` (which needs
    `owner`/`repo`/`path` for its own real, per-path 404 message); this
    covers the real cases this module's own new endpoints actually
    hit."""
    if response.status_code == 404:
        raise ValueError(f"{context} not found (or private and inaccessible with the configured token)")
    if response.status_code == 401:
        raise ValueError("the configured GitHub API token is invalid or has been revoked")
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        raise GitHubRateLimitError(f"GitHub API rate limit exceeded (resets at unix time {response.headers.get('X-RateLimit-Reset')})")
    response.raise_for_status()


async def github_get_repo(owner: str, repo: str) -> dict:
    """Item 2's own literal function -- reuses `fetch_github_repo`."""
    return await fetch_github_repo(owner, repo, settings.GITHUB_API_TOKEN)


async def github_list_issues(owner: str, repo: str, state: str = "all", labels: list[str] | None = None, since: str | None = None) -> list[dict]:
    """Item 2's own literal function -- reuses `fetch_github_issues`
    (real pull requests already excluded by that function's own logic)."""
    return await fetch_github_issues(owner, repo, settings.GITHUB_API_TOKEN, state=state, since=since, labels=labels)


async def github_get_issue(owner: str, repo: str, issue_number: int) -> dict:
    """Item 2's own literal function -- a real, new endpoint
    (`fetch_github_issues` only ever lists; this fetches exactly one)."""
    async with _client() as client:
        response = await client.get(f"{settings.GITHUB_API_BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}", headers=_headers())
    _raise_for_response(response, f"Issue {owner}/{repo}#{issue_number}")
    return response.json()


async def github_list_pull_requests(owner: str, repo: str, state: str = "open") -> list[dict]:
    """Item 2's own literal function -- GitHub's real, DEDICATED Pull
    Requests API (`/pulls`), not the Issues API `fetch_github_issues`
    deliberately excludes PRs from -- these are two real, separate
    endpoints, not the same data filtered differently."""
    async with _client() as client:
        response = await client.get(f"{settings.GITHUB_API_BASE_URL}/repos/{owner}/{repo}/pulls", headers=_headers(), params={"state": state, "per_page": 100})
    _raise_for_response(response, f"Pull requests for {owner}/{repo}")
    return response.json()


async def github_get_pull_request(owner: str, repo: str, pr_number: int) -> dict:
    """Item 2's own literal function."""
    async with _client() as client:
        response = await client.get(f"{settings.GITHUB_API_BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}", headers=_headers())
    _raise_for_response(response, f"Pull request {owner}/{repo}#{pr_number}")
    return response.json()


async def github_search_code(query: str, repo: str | None = None) -> list[dict]:
    """Item 2's own literal function -- GitHub's real Code Search API
    (`GET /search/code`), which genuinely REQUIRES an authenticated
    token (unlike every other real endpoint in this module) -- a real,
    honest, documented API constraint, not this module's own choice."""
    if not settings.GITHUB_API_TOKEN:
        raise ValueError("github_search_code requires a real, configured GITHUB_API_TOKEN -- GitHub's own Code Search API rejects unauthenticated requests")

    search_query = f"{query} repo:{repo}" if repo else query
    async with _client() as client:
        response = await client.get(f"{settings.GITHUB_API_BASE_URL}/search/code", headers=_headers(), params={"q": search_query})
    _raise_for_response(response, f"Code search for {query!r}")
    return response.json().get("items", [])
