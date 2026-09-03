"""
Partie 2.1.12/2.1.13 -- real network integration tests for
api/security/documents.py's own process_github_repo/process_github_issues:
the real fetch (a real, external, public GitHub repository, never
mocked) and the real filter/cap/fan-out decision-making, proven against
real targets (`octocat/Spoon-Knife` for files, `github/docs` for
issues -- see tests/test_github_extraction_integration.py's own module
docstring for why `github/docs` specifically for issues).

`process_github_files`/`process_github_issue_documents` (the next real
layer -- per-item Celery dispatch) are monkeypatched here to simply
CAPTURE what they are called with, rather than dragged through a live
broker or nested through a second `asyncio.run()` from within this
already-running one -- consistent with this codebase's own established
boundary (see tests/test_celery_integration.py's own module docstring,
and tests/test_sitemap_integration.py's own identical reasoning
earlier in this same cahier). The real, full per-item pipelines these
dispatches would go on to trigger (import_and_process_github_file/
import_and_process_github_issue -> process_document) are proven
separately, for real, in tests/test_documents_integration.py's own
GitHub sections.
"""

import uuid
from unittest.mock import patch

from api.security.documents import process_github_issues, process_github_repo
from api.services.github_extraction import fetch_github_repo, fetch_github_repo_tree

_REAL_OWNER, _REAL_REPO = "octocat", "Spoon-Knife"
_REAL_ISSUES_OWNER, _REAL_ISSUES_REPO = "github", "docs"


def _patch_process_github_files(captured):
    def _capture(organization_id, workspace_id, file_urls, created_by):
        captured["organization_id"] = organization_id
        captured["workspace_id"] = workspace_id
        captured["file_urls"] = file_urls
        captured["created_by"] = created_by
        return len(file_urls)

    return patch("api.security.documents.process_github_files", side_effect=_capture)


async def test_process_github_repo_runs_the_real_fetch_and_filters_against_a_real_repo():
    """
    Validation criterion: l'import d'un dépôt public fonctionne (sans
    token), les fichiers sont filtrés par extension -- against a real,
    external, non-mocked repository. `octocat/Spoon-Knife` has exactly
    one real file, `README.md`, which DOES match the real default
    include-pattern allowlist.
    """
    captured = {}
    organization_id, created_by = uuid.uuid4(), uuid.uuid4()

    with _patch_process_github_files(captured):
        result = await process_github_repo(organization_id, None, f"https://github.com/{_REAL_OWNER}/{_REAL_REPO}", None, 100, created_by)

    assert result == "completed"
    assert captured["organization_id"] == organization_id
    assert captured["workspace_id"] is None
    assert captured["created_by"] == created_by
    assert len(captured["file_urls"]) == 1
    assert "README.md" in captured["file_urls"][0]
    assert captured["file_urls"][0].startswith("https://api.github.com/repos/")


async def test_process_github_repo_excludes_files_that_do_not_match_the_real_patterns():
    """A real, narrow allowlist (`.py` only) against a real repo whose
    only real file is a `.md` -- must exclude it, not just narrow it."""
    captured = {}
    with _patch_process_github_files(captured):
        result = await process_github_repo(uuid.uuid4(), None, f"https://github.com/{_REAL_OWNER}/{_REAL_REPO}", [".py"], 100, uuid.uuid4())

    assert result == "completed"
    assert captured["file_urls"] == []


async def test_process_github_repo_enforces_a_real_max_files_cap():
    captured = {}
    with _patch_process_github_files(captured):
        await process_github_repo(uuid.uuid4(), None, f"https://github.com/{_REAL_OWNER}/{_REAL_REPO}", None, 0, uuid.uuid4())

    assert captured["file_urls"] == []


async def test_process_github_repo_returns_failed_for_a_real_nonexistent_repository():
    """Vision critique Q4's own answer, at the top-level repo-fetch
    boundary -- a real, live 404 (not a mock) ends this in a real,
    logged "failed" result, never a crash."""
    result = await process_github_repo(
        uuid.uuid4(), None, "https://github.com/this-owner-genuinely-does-not-exist-404/nope", None, 100, uuid.uuid4(),
    )
    assert result == "failed"


async def test_process_github_repo_agrees_with_an_independently_fetched_real_tree():
    """Cross-check: the real, independently-fetched file tree for this
    real target (3 real files: README.md, index.html, styles.css) has
    every one of its real entries captured by process_github_repo when
    given patterns that cover all three real extensions and a high
    enough max_files not to cap it -- proves process_github_repo is not
    silently dropping or duplicating real files somewhere in its own
    orchestration. Patterns are passed explicitly here rather than left
    as the real, narrower DEFAULT allowlist (github_include_patterns_list
    has no `.html`/`.css` entry) -- see the other tests above for that
    default-filtering behavior instead."""
    repo_data = await fetch_github_repo(_REAL_OWNER, _REAL_REPO, None)
    real_tree = await fetch_github_repo_tree(_REAL_OWNER, _REAL_REPO, repo_data["default_branch"], None)
    assert len(real_tree) > 1  # otherwise this cross-check would prove nothing

    captured = {}
    with _patch_process_github_files(captured):
        await process_github_repo(
            uuid.uuid4(), None, f"https://github.com/{_REAL_OWNER}/{_REAL_REPO}",
            [".md", ".html", ".css"], 10_000, uuid.uuid4(),
        )

    assert len(captured["file_urls"]) == len(real_tree)


def _patch_process_github_issue_documents(captured):
    def _capture(organization_id, workspace_id, issues_data, created_by):
        captured["organization_id"] = organization_id
        captured["workspace_id"] = workspace_id
        captured["issues_data"] = issues_data
        captured["created_by"] = created_by
        return len(issues_data)

    return patch("api.security.documents.process_github_issue_documents", side_effect=_capture)


async def test_process_github_issues_runs_the_real_fetch_and_assembles_real_issue_data():
    """
    Validation criterion: l'import d'issues fonctionne, les commentaires
    sont importés -- against a real, external, non-mocked repository.
    `max_issues=2` keeps the real number of per-issue comment fetches
    this test triggers small and deliberate.
    """
    captured = {}
    organization_id, created_by = uuid.uuid4(), uuid.uuid4()

    with _patch_process_github_issue_documents(captured):
        result = await process_github_issues(
            organization_id, None, f"https://github.com/{_REAL_ISSUES_OWNER}/{_REAL_ISSUES_REPO}",
            "open", None, None, 2, created_by,
        )

    assert result == "completed"
    assert captured["organization_id"] == organization_id
    assert captured["created_by"] == created_by
    assert len(captured["issues_data"]) == 2
    for entry in captured["issues_data"]:
        assert entry["issue"]["state"] == "open"
        # github/docs's own real open issues are all commented (confirmed
        # before writing this test) -- so real comments must have been
        # fetched for real, not left an empty placeholder.
        if entry["issue"]["comments"] > 0:
            assert len(entry["comments"]) > 0


async def test_process_github_issues_excludes_issues_that_do_not_match_a_real_label():
    """A real label that genuinely does not exist on this repository's
    real open issues -- must exclude everything, not just narrow it."""
    captured = {}
    with _patch_process_github_issue_documents(captured):
        result = await process_github_issues(
            uuid.uuid4(), None, f"https://github.com/{_REAL_ISSUES_OWNER}/{_REAL_ISSUES_REPO}",
            "open", None, ["this-label-genuinely-does-not-exist-anywhere"], 100, uuid.uuid4(),
        )

    assert result == "completed"
    assert captured["issues_data"] == []


async def test_process_github_issues_enforces_a_real_max_issues_cap():
    captured = {}
    with _patch_process_github_issue_documents(captured):
        await process_github_issues(
            uuid.uuid4(), None, f"https://github.com/{_REAL_ISSUES_OWNER}/{_REAL_ISSUES_REPO}", "open", None, None, 0, uuid.uuid4(),
        )

    assert captured["issues_data"] == []


async def test_process_github_issues_returns_failed_for_a_real_nonexistent_repository():
    """Vision critique Q3's own answer, at the top-level issues-fetch
    boundary -- a real, live 404 (not a mock) ends this in a real,
    logged "failed" result, never a crash."""
    result = await process_github_issues(
        uuid.uuid4(), None, "https://github.com/this-owner-genuinely-does-not-exist-404/nope",
        "all", None, None, 100, uuid.uuid4(),
    )
    assert result == "failed"
