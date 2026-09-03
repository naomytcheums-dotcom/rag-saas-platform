"""
Partie 2.1.12/2.1.13 -- fast-tier tests for api/services/github_extraction.py.
No real network call: every real HTTP interaction is exercised through
`httpx.MockTransport` (a REAL httpx testing utility -- request/response
parsing, headers, status codes, and JSON encoding/decoding all run for
real; only the actual network transport is swapped for a fake one that
resolves instantly and deterministically). This is the SAME "real
library behavior, fake network" split tests/test_url_fetching.py
already established for Partie 2.1.10's own SSRF-blocking tests.

Real, external-network-dependent behavior (an actual public repo, an
actual >1MB file, actual rate-limit headers) is verified once, for
real, in tests/test_github_extraction_integration.py instead.
"""

import base64

import httpx
import pytest
import yaml

from api.config import settings
from api.services.github_extraction import (
    GitHubRateLimitError,
    build_github_blob_url,
    build_github_contents_file_url,
    extract_github_metadata,
    extract_issue_metadata,
    fetch_github_file_content,
    fetch_github_files,
    fetch_github_issue_comments,
    fetch_github_issues,
    fetch_github_rate_limit_remaining,
    fetch_github_repo,
    fetch_github_repo_tree,
    format_issue_for_import,
    parse_github_contents_file_url,
    should_include_file,
    should_include_file_size,
    should_include_issue,
    validate_github_repo_url,
)


def _patch_client(monkeypatch, handler):
    """Points api/services/github_extraction.py's own `_client()` seam
    at a real httpx.AsyncClient backed by a fake MockTransport, exactly
    the way tests/test_url_fetching.py's own SSRF-blocking tests patch
    that module's own equivalent seam."""
    monkeypatch.setattr("api.services.github_extraction._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def _json_response(status_code: int, body: dict | list, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status_code, json=body, headers=headers or {})


# ------------------------------------------------------ validate_github_repo_url --

def test_validate_github_repo_url_accepts_the_plain_shape():
    assert validate_github_repo_url("https://github.com/octocat/Hello-World") == ("octocat", "Hello-World")


def test_validate_github_repo_url_tolerates_a_git_suffix_and_trailing_slash():
    assert validate_github_repo_url("https://github.com/octocat/Hello-World.git") == ("octocat", "Hello-World")
    assert validate_github_repo_url("https://github.com/octocat/Hello-World/") == ("octocat", "Hello-World")


def test_validate_github_repo_url_rejects_a_url_with_extra_path_segments():
    """Validation criterion -- this step's own literal scope is
    importing A REPOSITORY, not any GitHub URL shape."""
    with pytest.raises(ValueError):
        validate_github_repo_url("https://github.com/octocat/Hello-World/tree/main")


def test_validate_github_repo_url_rejects_a_non_github_host():
    with pytest.raises(ValueError):
        validate_github_repo_url("https://gitlab.com/octocat/Hello-World")


# ------------------------------------------------------------ fetch_github_repo --

async def test_fetch_github_repo_returns_the_real_response_body(monkeypatch):
    _patch_client(monkeypatch, lambda request: _json_response(200, {"full_name": "octocat/Hello-World", "default_branch": "master"}))
    data = await fetch_github_repo("octocat", "Hello-World", None)
    assert data == {"full_name": "octocat/Hello-World", "default_branch": "master"}


async def test_fetch_github_repo_attaches_the_authorization_header_only_when_a_token_is_given(monkeypatch):
    """Mirrors this step's own requested test shape ("mock de
    os.getenv('GITHUB_API_TOKEN')") at the layer where the token
    actually turns into an HTTP header -- captures the REAL outgoing
    request the mock transport receives."""
    captured = {}

    def handler(request):
        captured["authorization"] = request.headers.get("authorization")
        return _json_response(200, {})

    _patch_client(monkeypatch, handler)
    await fetch_github_repo("octocat", "Hello-World", "fake-token-for-unit-tests")
    assert captured["authorization"] == "Bearer fake-token-for-unit-tests"

    await fetch_github_repo("octocat", "Hello-World", None)
    assert captured["authorization"] is None


async def test_fetch_github_repo_raises_a_clear_error_for_a_404(monkeypatch):
    """Validation criterion: un dépôt invalide est rejeté (404)."""
    _patch_client(monkeypatch, lambda request: _json_response(404, {"message": "Not Found"}))
    with pytest.raises(ValueError, match="was not found, or is private"):
        await fetch_github_repo("nonexistent-owner", "nonexistent-repo", None)


async def test_fetch_github_repo_raises_a_clear_error_for_a_401(monkeypatch):
    """Validation criterion: un token invalide est rejeté (401)."""
    _patch_client(monkeypatch, lambda request: _json_response(401, {"message": "Bad credentials"}))
    with pytest.raises(ValueError, match="invalid or has been revoked"):
        await fetch_github_repo("octocat", "Hello-World", "a-bad-token")


async def test_fetch_github_repo_raises_a_distinguishable_rate_limit_error_when_remaining_is_zero(monkeypatch):
    """Validation criterion: le rate limit GitHub est géré via ses
    propres headers X-RateLimit-*."""
    _patch_client(monkeypatch, lambda request: _json_response(403, {"message": "rate limit exceeded"}, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1999999999"}))
    with pytest.raises(GitHubRateLimitError):
        await fetch_github_repo("octocat", "Hello-World", None)


async def test_fetch_github_repo_raises_a_plain_error_for_a_403_that_is_not_rate_limiting(monkeypatch):
    """A real 403 with real quota still remaining is a DIFFERENT real
    failure (e.g. an abuse-detection block) -- must not be
    misclassified as a rate-limit error."""
    _patch_client(monkeypatch, lambda request: _json_response(403, {"message": "forbidden"}, {"X-RateLimit-Remaining": "42"}))
    with pytest.raises(ValueError) as exc_info:
        await fetch_github_repo("octocat", "Hello-World", None)
    assert not isinstance(exc_info.value, GitHubRateLimitError)


# ----------------------------------------------------------- fetch_github_files --

async def test_fetch_github_files_lists_a_real_directorys_entries(monkeypatch):
    _patch_client(monkeypatch, lambda request: _json_response(200, [
        {"name": "README.md", "path": "README.md", "type": "file", "size": 13},
        {"name": "src", "path": "src", "type": "dir", "size": 0},
    ]))
    entries = await fetch_github_files("octocat", "Hello-World", "", None)
    assert [e["name"] for e in entries] == ["README.md", "src"]


async def test_fetch_github_files_normalizes_a_single_file_response_to_a_list(monkeypatch):
    """Real GitHub API quirk: a `path` pointing straight at a FILE
    (not a directory) returns one dict, not a list."""
    _patch_client(monkeypatch, lambda request: _json_response(200, {"name": "README.md", "path": "README.md", "type": "file"}))
    entries = await fetch_github_files("octocat", "Hello-World", "README.md", None)
    assert entries == [{"name": "README.md", "path": "README.md", "type": "file"}]


# --------------------------------------------------- fetch_github_file_content --

async def test_fetch_github_file_content_decodes_real_base64_content(monkeypatch):
    encoded = base64.b64encode(b"Hello World!\n").decode("ascii")
    _patch_client(monkeypatch, lambda request: _json_response(200, {"encoding": "base64", "content": encoded}))
    content = await fetch_github_file_content("octocat", "Hello-World", "README", None)
    assert content == b"Hello World!\n"


async def test_fetch_github_file_content_raises_for_a_file_github_declines_to_inline(monkeypatch):
    """Real GitHub Contents API behavior for a file over its own 1MB
    inline-content limit: `encoding: "none"`, `content: ""`."""
    _patch_client(monkeypatch, lambda request: _json_response(200, {"encoding": "none", "content": ""}))
    with pytest.raises(ValueError, match="has no inline content"):
        await fetch_github_file_content("octocat", "big-repo", "huge-file.csv", None)


async def test_fetch_github_file_content_sends_the_real_ref_as_a_query_parameter(monkeypatch):
    captured = {}

    def handler(request):
        captured["query"] = dict(request.url.params)
        return _json_response(200, {"encoding": "base64", "content": base64.b64encode(b"x").decode()})

    _patch_client(monkeypatch, handler)
    await fetch_github_file_content("octocat", "Hello-World", "README", None, ref="feature/x")
    assert captured["query"] == {"ref": "feature/x"}


# ------------------------------------------------------ fetch_github_repo_tree --

async def test_fetch_github_repo_tree_keeps_only_real_blob_entries(monkeypatch):
    """Validation criterion: les fichiers sont listés -- and only real,
    fetchable files, never a subdirectory or a submodule pointer."""
    _patch_client(monkeypatch, lambda request: _json_response(200, {
        "truncated": False,
        "tree": [
            {"path": "README.md", "type": "blob", "size": 13},
            {"path": "src", "type": "tree", "size": 0},
            {"path": "vendor/lib", "type": "commit", "size": 0},
        ],
    }))
    tree = await fetch_github_repo_tree("octocat", "Hello-World", "main", None)
    assert [entry["path"] for entry in tree] == ["README.md"]


async def test_fetch_github_repo_tree_does_not_raise_when_truncated(monkeypatch, caplog):
    """A real, honest limitation for an extraordinarily large repo --
    logged, never a crash or a silently incomplete result mistaken for
    a complete one."""
    _patch_client(monkeypatch, lambda request: _json_response(200, {"truncated": True, "tree": [{"path": "a", "type": "blob"}]}))
    tree = await fetch_github_repo_tree("octocat", "huge-repo", "main", None)
    assert len(tree) == 1


# ------------------------------------------------- fetch_github_rate_limit_remaining --

async def test_fetch_github_rate_limit_remaining_reads_the_real_core_bucket(monkeypatch):
    _patch_client(monkeypatch, lambda request: _json_response(200, {"resources": {"core": {"limit": 60, "remaining": 42, "reset": 123}}}))
    assert await fetch_github_rate_limit_remaining(None) == 42


# ----------------------------------------------------------- extract_github_metadata --

async def test_extract_github_metadata_reuses_already_fetched_repo_data_with_no_extra_request(monkeypatch):
    """Validation criterion: extraire les métadonnées (description,
    stars, forks, topics) -- and, this module's own deliberate
    addition, without a second, redundant real request when the caller
    already has the data."""
    def handler(request):
        raise AssertionError("must not make a real request when repo_data is already provided")

    _patch_client(monkeypatch, handler)
    repo_data = {"description": "My first repo", "stargazers_count": 5, "forks_count": 2, "topics": ["demo"], "default_branch": "master", "private": False}
    metadata = await extract_github_metadata("octocat", "Hello-World", repo_data=repo_data)
    assert metadata == {
        "owner": "octocat", "repo": "Hello-World", "description": "My first repo",
        "stars": 5, "forks": 2, "topics": ["demo"], "default_branch": "master", "private": False,
    }


async def test_extract_github_metadata_fetches_its_own_data_when_called_standalone(monkeypatch):
    _patch_client(monkeypatch, lambda request: _json_response(200, {"description": None, "stargazers_count": 0, "forks_count": 0, "topics": [], "default_branch": "main", "private": True}))
    metadata = await extract_github_metadata("octocat", "Hello-World")
    assert metadata["private"] is True
    assert metadata["description"] is None


# --------------------------------------------------- should_include_file(_size) --

def test_should_include_file_matches_by_real_extension():
    patterns = settings.github_include_patterns_list
    assert should_include_file("src/app.py", patterns) is True
    assert should_include_file("docs/readme.md", patterns) is True
    assert should_include_file("image.png", patterns) is False


def test_should_include_file_is_case_insensitive():
    assert should_include_file("README.MD", [".md"]) is True


def test_should_include_file_size_enforces_the_real_cap():
    assert should_include_file_size(500, 1000) is True
    assert should_include_file_size(1000, 1000) is True
    assert should_include_file_size(1001, 1000) is False


# ------------------------------------- contents-file-url build/parse round trip --

def test_build_and_parse_github_contents_file_url_round_trip():
    url = build_github_contents_file_url("octocat", "Hello-World", "src/app.py", "main")
    assert parse_github_contents_file_url(url) == ("octocat", "Hello-World", "src/app.py", "main")


def test_build_and_parse_github_contents_file_url_round_trip_with_a_slash_in_the_ref():
    """Real edge case this module's own docstring calls out explicitly
    -- a branch name containing a slash must not be confused with a
    path boundary."""
    url = build_github_contents_file_url("octocat", "Hello-World", "docs/readme.md", "feature/add-docs")
    assert parse_github_contents_file_url(url) == ("octocat", "Hello-World", "docs/readme.md", "feature/add-docs")


def test_build_and_parse_github_contents_file_url_round_trip_with_spaces_in_the_path():
    url = build_github_contents_file_url("octocat", "Hello-World", "my docs/read me.md", "main")
    assert parse_github_contents_file_url(url) == ("octocat", "Hello-World", "my docs/read me.md", "main")


def test_parse_github_contents_file_url_rejects_an_unrelated_url():
    with pytest.raises(ValueError):
        parse_github_contents_file_url("https://example.com/not-a-github-url")


def test_build_github_blob_url_is_a_real_human_clickable_github_com_url():
    assert build_github_blob_url("octocat", "Hello-World", "main", "src/app.py") == "https://github.com/octocat/Hello-World/blob/main/src/app.py"


# ------------------------------------------------------------ GitHub issues --

def _real_issue(number, state="open", labels=None, comments=0, is_pull_request=False, **overrides):
    """A real GitHub issue JSON shape, confirmed against a real
    response (expressjs/express) before writing this module."""
    issue = {
        "number": number, "title": f"Issue {number}", "state": state, "body": f"Body of issue {number}",
        "labels": [{"name": name} for name in (labels or [])],
        "assignees": [], "milestone": None, "user": {"login": "octocat"},
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-02T00:00:00Z", "closed_at": None,
        "html_url": f"https://github.com/octocat/Hello-World/issues/{number}", "comments": comments,
    }
    if is_pull_request:
        issue["pull_request"] = {"url": f"https://api.github.com/repos/octocat/Hello-World/pulls/{number}"}
    issue.update(overrides)
    return issue


def test_should_include_issue_matches_real_state():
    assert should_include_issue(_real_issue(1, state="open"), "open", None) is True
    assert should_include_issue(_real_issue(1, state="closed"), "open", None) is False
    assert should_include_issue(_real_issue(1, state="closed"), "all", None) is True
    assert should_include_issue(_real_issue(1, state="closed"), None, None) is True


def test_should_include_issue_uses_real_or_semantics_for_labels():
    """Real, deliberate finding: GitHub's own `labels` query param uses
    AND semantics -- should_include_issue deliberately uses OR instead
    (any ONE of the given labels matches), see this module's own
    docstring."""
    issue = _real_issue(1, labels=["docs", "bug"])
    assert should_include_issue(issue, "all", ["docs"]) is True
    assert should_include_issue(issue, "all", ["bug", "enhancement"]) is True
    assert should_include_issue(issue, "all", ["enhancement"]) is False
    assert should_include_issue(issue, "all", None) is True


async def test_fetch_github_issues_paginates_and_excludes_real_pull_requests(monkeypatch):
    """Validation criterion: l'import d'issues fonctionne -- and real
    pull requests (GitHub's Issues API returns both from the same
    endpoint) are never mistaken for one."""
    pages = {
        "1": [_real_issue(3, is_pull_request=True), _real_issue(2), _real_issue(1)],
        "2": [],
    }

    def handler(request):
        page = request.url.params.get("page")
        return httpx.Response(200, json=pages.get(page, []))

    _patch_client(monkeypatch, handler)
    issues = await fetch_github_issues("octocat", "Hello-World", None)
    assert [i["number"] for i in issues] == [2, 1]


async def test_fetch_github_issues_stops_at_the_first_empty_page(monkeypatch):
    calls = []

    def handler(request):
        page = request.url.params.get("page")
        calls.append(page)
        if page == "1":
            return httpx.Response(200, json=[_real_issue(1)])
        return httpx.Response(200, json=[])

    _patch_client(monkeypatch, handler)
    issues = await fetch_github_issues("octocat", "Hello-World", None)
    assert [i["number"] for i in issues] == [1]
    assert calls == ["1", "2"]


async def test_fetch_github_issues_sends_real_state_and_since_to_the_api_but_not_labels(monkeypatch):
    """Real, deliberate finding documented in this module -- `labels`
    is applied client-side (should_include_issue), NEVER forwarded to
    GitHub's own query string, to avoid its real AND semantics
    silently excluding matches a caller would expect with OR."""
    captured = {}

    def handler(request):
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=[])

    _patch_client(monkeypatch, handler)
    await fetch_github_issues("octocat", "Hello-World", None, state="open", since="2024-01-01T00:00:00Z", labels=["docs"])
    assert captured["params"]["state"] == "open"
    assert captured["params"]["since"] == "2024-01-01T00:00:00Z"
    assert "labels" not in captured["params"]


async def test_fetch_github_issues_applies_the_real_label_filter_while_paginating(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(200, json=[
        _real_issue(1, labels=["docs"]), _real_issue(2, labels=["bug"]),
    ] if request.url.params.get("page") == "1" else []))
    issues = await fetch_github_issues("octocat", "Hello-World", None, labels=["docs"])
    assert [i["number"] for i in issues] == [1]


async def test_fetch_github_issue_comments_returns_real_comments(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(200, json=[
        {"user": {"login": "alice"}, "body": "First comment", "created_at": "2026-01-01T00:00:00Z"},
    ]))
    comments = await fetch_github_issue_comments("octocat", "Hello-World", 1, None)
    assert comments[0]["user"]["login"] == "alice"


def test_extract_issue_metadata_reports_title_state_labels_assignees_milestone():
    issue = _real_issue(
        42, state="closed", labels=["bug", "priority-high"],
        assignees=[{"login": "alice"}, {"login": "bob"}],
        milestone={"title": "v2.0"}, user={"login": "carol"},
    )
    metadata = extract_issue_metadata(issue)
    assert metadata["number"] == 42
    assert metadata["state"] == "closed"
    assert metadata["labels"] == ["bug", "priority-high"]
    assert metadata["assignees"] == ["alice", "bob"]
    assert metadata["milestone"] == "v2.0"
    assert metadata["author"] == "carol"
    assert metadata["html_url"] == "https://github.com/octocat/Hello-World/issues/42"


def test_extract_issue_metadata_handles_a_real_issue_with_no_milestone_or_assignees():
    metadata = extract_issue_metadata(_real_issue(1))
    assert metadata["milestone"] is None
    assert metadata["assignees"] == []


def test_format_issue_for_import_produces_real_markdown_with_title_body_and_comments():
    """Validation criterion / vision critique Q1: issues are imported
    as documents, formatted as real Markdown (title + body +
    comments), with real YAML frontmatter FIRST -- see this function's
    own docstring for the real CI bug (metadata_json silently
    overwritten by process_document) this frontmatter fixes: Partie
    2.1.4's own real extract_markdown_metadata recovers it naturally."""
    issue = _real_issue(7, labels=["docs"], user={"login": "carol"})
    comments = [{"user": {"login": "alice"}, "body": "Thanks for reporting!"}]
    markdown = format_issue_for_import(issue, comments)
    assert markdown.startswith("---\n")
    frontmatter, _sep, body = markdown[4:].partition("\n---\n")
    real_metadata = yaml.safe_load(frontmatter)
    assert real_metadata["number"] == 7
    assert real_metadata["labels"] == ["docs"]
    assert real_metadata["author"] == "carol"
    assert body.strip().startswith("# Issue 7")
    assert "**Labels:** docs" in markdown
    assert "**Author:** carol" in markdown
    assert "Body of issue 7" in markdown
    assert "## Comment by alice" in markdown
    assert "Thanks for reporting!" in markdown


def test_format_issue_for_import_handles_a_real_issue_with_no_body_or_comments():
    issue = _real_issue(1, body=None)
    markdown = format_issue_for_import(issue, None)
    assert markdown.startswith("---\n")
    assert markdown.strip().endswith("**Author:** octocat")  # no body/comments -- ends right after the metadata block
    assert "## Comment by" not in markdown
