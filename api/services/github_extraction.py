"""
Partie 2.1.12/2.1.13 -- fetching a GitHub repository's real metadata,
files, and issues via GitHub's REST API, for import into a knowledge
base. Uses a plain
`httpx.AsyncClient` against a FIXED, admin-configured host
(`settings.GITHUB_API_BASE_URL`, `api.github.com` by default) --
unlike Partie 2.1.10's `fetch_url_content`, this deliberately does NOT
go through that module's own SSRF-safe custom transport: the real
target host here is never caller-controlled (only `owner`/`repo` PATH
SEGMENTS on that one fixed host are), the same "plain
`httpx.AsyncClient` against a trusted, fixed external API" pattern this
codebase already uses for the Have I Been Pwned check
(`api/security/password_strength.py`) and enterprise OIDC discovery
(`api/security/enterprise_oidc.py`) -- SSRF protection exists
specifically for requests to a caller-SUPPLIED host, which this feature
never makes.

**Real GitHub API behavior, verified before writing this module, not
assumed**:
- Unauthenticated requests are real and allowed (60/hour), just at a
  much lower rate than an authenticated token (5,000/hour) -- confirmed
  for real against a real public repo (`octocat/Hello-World`).
- A repo that doesn't exist AND a real, existing PRIVATE repo accessed
  without sufficient access both return the exact same 404 -- confirmed
  for real. A deliberate GitHub anti-enumeration design, not a bug:
  there is genuinely no way to tell "wrong owner/repo" apart from "real
  private repo, no valid token" from outside, and this module does not
  pretend otherwise (see `_raise_for_github_response`'s own message).
- An actually-INVALID token (malformed or revoked) gets its own real,
  distinguishable 401 -- confirmed for real.
- Every real response (success or failure) carries real
  `X-RateLimit-Limit`/`X-RateLimit-Remaining`/`X-RateLimit-Reset`
  headers -- confirmed for real, on both authenticated and
  unauthenticated requests. `GET /rate_limit` reports the same numbers
  on demand and, per GitHub's own documentation, does NOT itself count
  against the quota -- used here to decide, proactively, how many real
  per-file requests can safely be scheduled (vision critique Q3/Q4's
  own "le rate limiting est-il respecté" answer), rather than reacting
  only after a real 403 already happened partway through an import.
- The Contents API returns a file's content inline as base64 ONLY up to
  1MB -- confirmed for real against a real >1MB file (a real COVID-19
  case-count CSV in a real public repo): `encoding` becomes `"none"`,
  `content` becomes `""`, and a `download_url` pointing to an ENTIRELY
  DIFFERENT host (`raw.githubusercontent.com`) appears instead.
  `GITHUB_MAX_FILE_SIZE`'s own literal 1MB default matches this real
  API limit -- not a coincidence: filtering files by real size BEFORE
  ever requesting their content (`should_include_file_size` below,
  applied by `api/security/documents.py`'s `process_github_repo`)
  means this module never needs a second real HTTP client path to that
  second host at all.
- The recursive Git Trees API (`GET .../git/trees/{sha}?recursive=1`)
  returns a repo's ENTIRE real file tree in ONE real request, each real
  entry carrying its own `path`/`size`/`type` -- confirmed for real
  against a real repo. Used here (`fetch_github_repo_tree`, not one of
  this step's own literal functions, a deliberate addition) instead of
  crawling every directory one real `fetch_github_files` call at a
  time, since that would cost one real, rate-limited request PER real
  directory for no benefit. A real `truncated: true` flag (GitHub's own
  safety cap, roughly 100,000 entries/7MB) is checked and logged -- an
  honest, stated limitation for an extraordinarily large repository,
  never silently ignored.
- GitHub's real Issues REST endpoint (`GET /repos/{owner}/{repo}/issues`)
  returns real PULL REQUESTS too, not just real issues -- confirmed for
  real against a real, active repository (`expressjs/express`): GitHub
  internally treats a PR as a special kind of issue, and the ONLY real,
  documented way to tell them apart is a real `pull_request` key present
  on the JSON object (real issues never have one). `fetch_github_issues`
  below always excludes these -- never one of this step's own real
  "issues" (vision critique Q1's own answer: only real issues, never a
  PR mistaken for one, get imported).
- GitHub's own real `labels` query parameter uses AND semantics -- an
  issue must carry EVERY listed label, confirmed for real
  (`labels=docs,tests` returned only the one real issue that had BOTH),
  not "any of these labels" the way a caller would more naturally read
  a "filter by labels" request. `fetch_github_issues` therefore does
  NOT forward `labels` to the real API at all -- `should_include_issue`
  applies it CLIENT-side instead, with real OR semantics (matching
  Partie 2.1.11's own sitemap `filter_sitemap_urls` precedent: any one
  of the given patterns/labels matches).
- `since` accepts a real ISO 8601 string with either a bare `Z` suffix
  or a real `+00:00` offset -- confirmed for real, both work -- but a
  malformed one, or an invalid `state`, each get their own real,
  distinct `422` from GitHub's own API (confirmed for real against both)
  -- `GitHubIssuesImportRequest`'s own `state` field is constrained at
  this server's OWN schema layer instead, a real, structural 422 of
  this server's own before ever reaching GitHub for that specific case.
"""

import base64
import logging
import re
from urllib.parse import parse_qs, quote, unquote, urlsplit

import httpx

from api.config import settings
from api.services.url_fetching import USER_AGENT

logger = logging.getLogger(__name__)

_API_VERSION = "2022-11-28"
_TIMEOUT_SECONDS = 15.0

# GitHub's own real username/repo-name rules (usernames: 1-39 chars,
# alphanumeric or hyphen; repo names: alphanumeric, hyphen, underscore,
# period) -- a real `.git` suffix and a trailing slash are both real,
# common ways to write the same URL, tolerated and stripped here rather
# than rejected. Deliberately GitHub.com ONLY, not a GitHub Enterprise
# Server host (which typically uses a DIFFERENT host for its API than
# for its own web UI, a genuinely more complex case nobody asked for --
# same "don't build for a hypothetical nobody requested" restraint as
# Partie 2.1.10's own Playwright decision).
_GITHUB_REPO_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})?)/(?P<repo>[A-Za-z0-9._-]+?)(?:\.git)?/?$"
)


class GitHubRateLimitError(ValueError):
    """A real, distinguishable subclass of the same `ValueError` every
    other real failure in this module raises -- so an ordinary caller
    that only cares about "did this fail" keeps working unchanged
    (`except ValueError` still catches it), while `process_github_repo`
    (vision critique Q4's own "si le rate limit est atteint" answer)
    can tell "genuinely rate limited, stop scheduling more real
    requests" apart from every other real failure."""


def validate_github_repo_url(url: str) -> tuple[str, str]:
    """Item 1's literal validation, exposed as its own real function --
    real, pure, no network. Returns the real `(owner, repo)` pair; a
    URL carrying anything beyond a bare `owner/repo` (e.g. `.../tree/main`,
    `.../issues`) is deliberately rejected -- this step's own literal
    scope is importing A REPOSITORY, not any GitHub URL shape."""
    match = _GITHUB_REPO_URL_RE.match(url.strip())
    if not match:
        raise ValueError(f"'{url}' is not a valid GitHub repository URL (expected https://github.com/{{owner}}/{{repo}})")
    return match.group("owner"), match.group("repo")


def _client() -> httpx.AsyncClient:
    """One shared client config -- also the one seam
    tests/test_github_extraction.py patches (via `httpx.MockTransport`,
    a REAL httpx testing utility that still runs httpx's own real
    request/response parsing, only swapping the actual network
    transport) to exercise this module's real HTTP logic with no real
    network call. Same "one small factory function, easy to monkeypatch"
    shape as api/services/url_fetching.py's own `_client()`."""
    return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)


def _headers(token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": _API_VERSION, "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _raise_for_github_response(response: httpx.Response, owner: str, repo: str, path: str | None = None) -> None:
    """Real status-code mapping, verified against real responses before
    writing this (see this module's own docstring) -- one real,
    distinguishable `ValueError` (or the `GitHubRateLimitError`
    subclass) per real, distinguishable GitHub failure mode. `path`,
    when given (fetch_github_files/fetch_github_file_content, both real
    Contents API calls against a specific path), makes the real 404
    message accurate for the MORE common case once a repo import is
    already underway: the repo itself is real and accessible (already
    confirmed by fetch_github_repo before any per-file call happens),
    but this ONE real path inside it doesn't exist -- confirmed for
    real to be indistinguishable from "repo private, no token" via the
    exact same 404, same as at the repo level."""
    if response.status_code == 404:
        target = f"{owner}/{repo}/{path}" if path else f"{owner}/{repo}"
        reason = "or its repository is" if path else "or is"
        raise ValueError(
            f"'{target}' was not found, {reason} private and inaccessible with the configured token -- "
            "GitHub's own API deliberately returns the same 404 for both cases, to avoid revealing a private repository's existence."
        )
    if response.status_code == 401:
        raise ValueError("the configured GitHub API token is invalid or has been revoked")
    if response.status_code == 403:
        if response.headers.get("X-RateLimit-Remaining") == "0":
            raise GitHubRateLimitError(
                f"GitHub API rate limit exceeded (resets at unix time {response.headers.get('X-RateLimit-Reset')})"
            )
        raise ValueError(f"GitHub API request for '{owner}/{repo}' was forbidden: {response.text}")
    if response.status_code == 422:
        # Real, confirmed finding (Partie 2.1.13): an invalid `state` or
        # a malformed `since` both get their own real, distinct 422 from
        # GitHub's own Issues API -- api/schemas/documents.py's own
        # GitHubIssuesImportRequest already rejects an invalid `state`
        # with a real, structural 422 of THIS server's own before ever
        # reaching GitHub, so this branch is mainly a safety net for
        # fetch_github_issues called directly/standalone.
        raise ValueError(f"GitHub API rejected this request for '{owner}/{repo}' as invalid: {response.text}")
    response.raise_for_status()


async def fetch_github_repo(owner: str, repo: str, token: str | None) -> dict:
    """Item 3's literal function -- real repository metadata."""
    async with _client() as client:
        response = await client.get(f"{settings.GITHUB_API_BASE_URL}/repos/{owner}/{repo}", headers=_headers(token))
    _raise_for_github_response(response, owner, repo)
    return response.json()


async def fetch_github_files(owner: str, repo: str, path: str, token: str | None) -> list[dict]:
    """Item 3's literal function -- lists one real directory's entries
    via the Contents API. Real, honest, documented GitHub limitation: a
    single directory listing is capped at 1,000 real entries with no
    further pagination -- a directory beyond that needs the recursive
    Trees API `fetch_github_repo_tree` below uses for a full-repo crawl
    instead. A real, single FILE path (not a directory) returns one
    dict, not a list -- normalized to a one-item list here so callers
    always get the same shape regardless of what `path` pointed to."""
    async with _client() as client:
        response = await client.get(
            f"{settings.GITHUB_API_BASE_URL}/repos/{owner}/{repo}/contents/{quote(path)}", headers=_headers(token),
        )
    _raise_for_github_response(response, owner, repo, path=path)
    entries = response.json()
    return [entries] if isinstance(entries, dict) else entries


async def fetch_github_file_content(owner: str, repo: str, path: str, token: str | None, ref: str | None = None) -> bytes:
    """Item 3's literal function (+ this module's own optional `ref` --
    the exact commit/branch to read from, so a per-file fetch can
    target the SAME real tree `process_github_repo` already resolved,
    rather than silently drifting to whatever the default branch
    happens to be by the time this runs). Real file content, decoded
    from GitHub's own base64 encoding. Raises `ValueError` for a file
    GitHub itself declines to inline (`encoding != "base64"`, genuinely
    only possible for a file over the real Contents API's own 1MB limit
    -- see this module's own docstring for why `should_include_file_size`
    is meant to filter these out BEFORE this function is ever called,
    making this a safety net, not the normal path)."""
    params = {"ref": ref} if ref else None
    async with _client() as client:
        response = await client.get(
            f"{settings.GITHUB_API_BASE_URL}/repos/{owner}/{repo}/contents/{quote(path)}",
            headers=_headers(token), params=params,
        )
    _raise_for_github_response(response, owner, repo, path=path)
    entry = response.json()
    if entry.get("encoding") != "base64":
        raise ValueError(
            f"'{owner}/{repo}/{path}' has no inline content available (GitHub's own real Contents API limit is 1MB) -- "
            "should_include_file_size should have excluded this file before it ever reached this function"
        )
    return base64.b64decode(entry["content"])


async def fetch_github_repo_tree(owner: str, repo: str, ref: str, token: str | None) -> list[dict]:
    """NOT one of this step's own literal functions -- a real,
    deliberate addition (see this module's own docstring, vision
    critique Q3): the real, recursive Git Trees API lists a repo's
    ENTIRE file tree in ONE real request, at a MUCH lower real
    rate-limit cost than crawling every directory one at a time via
    `fetch_github_files` above. Returns only real `"blob"` entries
    (actual files) -- a real `"tree"` entry is a subdirectory (already
    walked by the SAME recursive response) and a real `"commit"` entry
    is a submodule pointer, neither of which is real, fetchable file
    content."""
    async with _client() as client:
        response = await client.get(
            f"{settings.GITHUB_API_BASE_URL}/repos/{owner}/{repo}/git/trees/{quote(ref)}",
            headers=_headers(token), params={"recursive": "1"},
        )
    _raise_for_github_response(response, owner, repo)
    body = response.json()
    if body.get("truncated"):
        logger.warning(
            "fetch_github_repo_tree: '%s/%s' own real file tree was truncated by GitHub's own size cap -- "
            "not every file in this repository could be listed", owner, repo,
        )
    return [entry for entry in body.get("tree", []) if entry.get("type") == "blob"]


async def fetch_github_rate_limit_remaining(token: str | None) -> int:
    """Real, on-demand quota check (see this module's own docstring for
    why `GET /rate_limit` is used, and why it's free) -- reports the
    `"core"` bucket's own real remaining count, the one every call in
    this module actually draws from."""
    async with _client() as client:
        response = await client.get(f"{settings.GITHUB_API_BASE_URL}/rate_limit", headers=_headers(token))
    response.raise_for_status()
    return response.json()["resources"]["core"]["remaining"]


async def extract_github_metadata(owner: str, repo: str, token: str | None = None, repo_data: dict | None = None) -> dict:
    """Item 3's literal function (+ this module's own optional `token`/
    `repo_data` extras): `repo_data`, if already fetched by a caller
    (`api/security/documents.py`'s `process_github_repo` always has
    already called `fetch_github_repo` for its own needs), is reused
    directly rather than this function making a SECOND real, redundant,
    rate-limited request for the exact same repository -- a real waste
    this step's own literal 2-argument signature would otherwise cause
    every single time. Falls back to fetching it itself when called on
    its own, so the literal signature still works standalone."""
    if repo_data is None:
        repo_data = await fetch_github_repo(owner, repo, token)
    return {
        "owner": owner,
        "repo": repo,
        "description": repo_data.get("description"),
        "stars": repo_data.get("stargazers_count", 0),
        "forks": repo_data.get("forks_count", 0),
        "topics": repo_data.get("topics", []),
        "default_branch": repo_data.get("default_branch"),
        "private": repo_data.get("private", False),
    }


def should_include_file(file_path: str, patterns: list[str]) -> bool:
    """Item 4's literal function -- real extension-based ALLOWLIST
    match (see this module's own docstring, and `api/config.py`'s own
    `github_include_patterns_list`, for why this is an allowlist, not
    an optional narrowing filter the way Partie 2.1.11's sitemap
    `filters` is)."""
    return any(file_path.lower().endswith(pattern.lower()) for pattern in patterns)


def should_include_file_size(file_size: int, max_size: int) -> bool:
    """Item 4's literal function."""
    return file_size <= max_size


_GITHUB_CONTENTS_FILE_URL_RE = re.compile(r"^/repos/(?P<owner>[^/]+)/(?P<repo>[^/]+)/contents/(?P<path>.+)$")


def parse_github_contents_file_url(file_url: str) -> tuple[str, str, str, str | None]:
    """Real, deliberate internal encoding, not one of this step's own
    literal functions: `api/security/documents.py`'s `process_github_repo`
    builds each real per-file `file_url` as the exact, directly-usable
    GitHub Contents API url for that one file -- `owner`/`repo`/`path`
    as real URL PATH segments, `ref` (the exact branch/commit this
    file's own listing was resolved against) as a query parameter.
    Query, not a path segment, deliberately: a real branch name can
    itself contain a slash (e.g. `feature/x`), which would make `ref`
    ambiguous with the start of `path` if it were a path segment too.
    Parsed back out here rather than threading owner/repo/path/ref as
    four separate Celery task arguments -- matching this step's own
    literal `process_github_file_task(file_url, ...)` signature."""
    parts = urlsplit(file_url)
    match = _GITHUB_CONTENTS_FILE_URL_RE.match(parts.path)
    if not match:
        raise ValueError(f"'{file_url}' is not a real GitHub contents file url")
    ref = parse_qs(parts.query).get("ref", [None])[0]
    return unquote(match.group("owner")), unquote(match.group("repo")), unquote(match.group("path")), (unquote(ref) if ref else None)


def build_github_contents_file_url(owner: str, repo: str, path: str, ref: str) -> str:
    """The exact inverse of `parse_github_contents_file_url` above --
    kept as its own real, named function (rather than an inline
    f-string in `process_github_repo`) so the two stay obviously in
    sync."""
    return f"{settings.GITHUB_API_BASE_URL}/repos/{owner}/{repo}/contents/{quote(path)}?ref={quote(ref)}"


def build_github_blob_url(owner: str, repo: str, ref: str, path: str) -> str:
    """A real, human-clickable `github.com` URL (as opposed to the
    machine-oriented `api.github.com` one `build_github_contents_file_url`
    builds) -- used as `Document.source_url`, the same real-provenance
    column Partie 2.1.10 already added, reused unchanged here (no new
    column needed for this step)."""
    return f"https://github.com/{owner}/{repo}/blob/{ref}/{path}"


def should_include_issue(issue: dict, state: str | None, labels: list[str] | None) -> bool:
    """Item 3's literal function -- real state match (GitHub's own API
    already applies `state` server-side by the time `fetch_github_issues`
    calls this, but this is still a real, standalone, correct check on
    its own, for a caller that uses it directly) and a real, OR-based
    label match -- see this module's own docstring for why OR, not
    GitHub's own AND."""
    if state and state != "all" and issue.get("state") != state:
        return False
    if labels:
        issue_labels = {label["name"] for label in issue.get("labels", [])}
        if not issue_labels.intersection(labels):
            return False
    return True


# Real safety cap on how many real PAGES of issues fetch_github_issues
# will fetch (100 real issues/page) -- protects the FETCH phase itself
# from a repository with an enormous real issue tracker, independent of
# process_github_issues's own `max_issues` (applied afterward, at the
# orchestration level -- same "filter before cap" ordering Partie
# 2.1.11/2.1.12 already established).
_MAX_ISSUE_PAGES = 50


async def fetch_github_issues(
    owner: str, repo: str, token: str | None, state: str = "all",
    since: str | None = None, labels: list[str] | None = None,
) -> list[dict]:
    """Item 2's literal function -- paginates through GitHub's real
    Issues API. `state`/`since` are both sent to the real API (neither
    has GitHub's own labels ambiguity -- state is one exact value,
    since is a real, documented `updated_at >=` cutoff); `labels` is
    applied CLIENT-side via `should_include_issue` instead (see this
    module's own docstring for why). Real pull requests are always
    excluded first, before the label check even runs."""
    params = {"state": state, "per_page": 100}
    if since:
        params["since"] = since

    matched: list[dict] = []
    async with _client() as client:
        for page in range(1, _MAX_ISSUE_PAGES + 1):
            response = await client.get(
                f"{settings.GITHUB_API_BASE_URL}/repos/{owner}/{repo}/issues",
                headers=_headers(token), params={**params, "page": page},
            )
            _raise_for_github_response(response, owner, repo)
            batch = response.json()
            if not batch:
                break
            matched.extend(
                item for item in batch if "pull_request" not in item and should_include_issue(item, state, labels)
            )
    return matched


async def fetch_github_issue_comments(owner: str, repo: str, issue_number: int, token: str | None) -> list[dict]:
    """Item 2's literal function -- real comments for one real issue."""
    async with _client() as client:
        response = await client.get(
            f"{settings.GITHUB_API_BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments", headers=_headers(token),
        )
    _raise_for_github_response(response, owner, repo)
    return response.json()


def extract_issue_metadata(issue: dict) -> dict:
    """Item 2's literal function -- titre, état, labels, assignés,
    milestone, plus a few more real fields (author, timestamps, the
    real html_url, comment count) genuinely useful to keep alongside
    them in `Document.metadata_json`."""
    return {
        "number": issue["number"],
        "title": issue["title"],
        "state": issue["state"],
        "labels": [label["name"] for label in issue.get("labels", [])],
        "assignees": [assignee["login"] for assignee in issue.get("assignees", [])],
        "milestone": issue["milestone"]["title"] if issue.get("milestone") else None,
        "author": issue.get("user", {}).get("login") if issue.get("user") else None,
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "closed_at": issue.get("closed_at"),
        "html_url": issue.get("html_url"),
        "comment_count": issue.get("comments", 0),
    }


def format_issue_for_import(issue: dict, comments: list[dict] | None = None) -> str:
    """Item 2's literal function -- titre + corps + commentaires,
    formatted as real Markdown (vision critique Q1's own answer: yes,
    so this flows through Partie 2.1.4's own real Markdown extraction
    pipeline -- real heading-based sectioning included -- completely
    unchanged, the same "reuse the existing pipeline" story as every
    GitHub-sourced import so far)."""
    metadata = extract_issue_metadata(issue)
    lines = [f"# {metadata['title']}", "", f"- **State:** {metadata['state']}"]
    if metadata["labels"]:
        lines.append(f"- **Labels:** {', '.join(metadata['labels'])}")
    if metadata["assignees"]:
        lines.append(f"- **Assignees:** {', '.join(metadata['assignees'])}")
    if metadata["milestone"]:
        lines.append(f"- **Milestone:** {metadata['milestone']}")
    if metadata["author"]:
        lines.append(f"- **Author:** {metadata['author']}")
    lines.append("")
    if issue.get("body"):
        lines.append(issue["body"])
        lines.append("")
    for comment in comments or []:
        author = comment.get("user", {}).get("login") if comment.get("user") else "unknown"
        lines.append(f"## Comment by {author}")
        lines.append("")
        lines.append(comment.get("body") or "")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
