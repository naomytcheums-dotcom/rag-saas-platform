"""
Partie 2.1.12 -- real network tests for api/services/github_extraction.py.
Unlike tests/test_github_extraction.py (whose tests never reach the
real network at all), these actually reach the real GitHub REST API,
unauthenticated, against `octocat/Hello-World` and `octocat/Spoon-Knife`
-- GitHub's own real, stable, first-party demo repositories, chosen
instead of some other real project precisely so this test suite is
never mistaken for a crawler hitting a real third-party production
project.

Every call here passes `token=None` explicitly -- never
`settings.GITHUB_API_TOKEN` -- so these "public repo, no token needed"
tests behave identically regardless of whatever token this environment
happens to have configured (this session's own CI, for instance, sets
no real GitHub token at all -- see tests/test_documents.py's own
GitHub section for why a token is never read from ambient settings in
a test that specifically means to prove "no token needed").

A real PRIVATE repo import (needing a real, valid GITHUB_API_TOKEN
pointing at a repo this session does not control) is not something an
automated CI run can responsibly provision -- same restraint as Partie
2.1.1's own S3_DOCUMENTS_BUCKET_NAME (never auto-provisioned).
"""

from api.services.github_extraction import (
    extract_github_metadata,
    fetch_github_file_content,
    fetch_github_files,
    fetch_github_rate_limit_remaining,
    fetch_github_repo,
    fetch_github_repo_tree,
)


async def test_fetch_github_repo_returns_real_metadata_for_a_real_public_repo():
    """Validation criterion: l'import d'un dépôt public fonctionne
    (sans token)."""
    data = await fetch_github_repo("octocat", "Hello-World", None)
    assert data["full_name"] == "octocat/Hello-World"
    assert data["private"] is False


async def test_fetch_github_repo_raises_for_a_real_nonexistent_repo():
    """Validation criterion: un dépôt invalide est rejeté (404)."""
    try:
        await fetch_github_repo("this-owner-genuinely-does-not-exist-404", "nope", None)
        raise AssertionError("expected a ValueError for a real nonexistent repo")
    except ValueError as exc:
        assert "was not found" in str(exc)


async def test_fetch_github_repo_raises_for_a_real_invalid_token():
    """Validation criterion: un token invalide est rejeté (401)."""
    try:
        await fetch_github_repo("octocat", "Hello-World", "ghp_totally_invalid_token_for_testing_xyz")
        raise AssertionError("expected a ValueError for a real invalid token")
    except ValueError as exc:
        assert "invalid" in str(exc)


async def test_extract_github_metadata_reports_real_description_stars_forks_topics():
    """Validation criterion: extraire les métadonnées (description,
    stars, forks, topics) -- against real, live numbers."""
    metadata = await extract_github_metadata("octocat", "Hello-World", None)
    assert metadata["description"]
    assert metadata["stars"] > 0
    assert isinstance(metadata["forks"], int)
    assert isinstance(metadata["topics"], list)


async def test_fetch_github_files_lists_a_real_public_repos_root():
    files = await fetch_github_files("octocat", "Spoon-Knife", "", None)
    assert any(entry["name"] == "README.md" for entry in files)


async def test_fetch_github_file_content_downloads_and_decodes_a_real_file():
    content = await fetch_github_file_content("octocat", "Hello-World", "README", None)
    assert content == b"Hello World!\n"


async def test_fetch_github_repo_tree_lists_the_entire_real_repo_in_one_call():
    """Validation criterion: les fichiers sont listés -- via the real
    recursive Trees API this module deliberately uses instead of
    crawling directories one at a time (vision critique Q3)."""
    repo_data = await fetch_github_repo("octocat", "Spoon-Knife", None)
    tree = await fetch_github_repo_tree("octocat", "Spoon-Knife", repo_data["default_branch"], None)
    assert any(entry["path"] == "README.md" for entry in tree)
    assert all(entry["type"] == "blob" for entry in tree)


async def test_fetch_github_rate_limit_remaining_reports_a_real_number():
    remaining = await fetch_github_rate_limit_remaining(None)
    assert isinstance(remaining, int)
    assert remaining >= 0
