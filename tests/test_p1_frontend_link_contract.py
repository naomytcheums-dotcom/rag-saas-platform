"""MAP-001 / MAP-002 / MAP-003: every link the backend puts in an e-mail or a redirect must land on a page that exists.

The invitation link (`/invitations/accept`) and the OAuth/SSO return (`/oauth-callback`) pointed to pages that did not exist, so inviting a
member and signing in with Google/GitHub/SSO could never complete in the interface. This contract test extracts the frontend paths built
from FRONTEND_URL in api/ and checks that a `frontend/app/<path>/page.tsx` exists. Paths still without a page are listed explicitly (the
test fails when one is fixed without shrinking the list, and when a new gap appears)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"FRONTEND_URL[^}\n]*\}/([a-z0-9][a-z0-9\-/]*)")

# MAP-003 (P2), not fixed yet: account restoration, consent reactivation and 2FA lockout recovery confirmation pages.
KNOWN_MISSING_PAGES = {"restore-account", "reactivate-consent", "2fa-lockout-recovery"}


def _linked_paths() -> set[str]:
    found = set()
    for source in (ROOT / "api").rglob("*.py"):
        found.update(LINK.findall(source.read_text(encoding="utf-8")))
    return found


def _has_page(path: str) -> bool:
    return (ROOT / "frontend" / "app" / path / "page.tsx").exists()


def test_the_extraction_finds_the_links_the_audit_named():
    assert {"invitations/accept", "oauth-callback", "reset-password", "register"} <= _linked_paths()


def test_the_invitation_and_oauth_pages_exist():
    assert _has_page("invitations/accept")
    assert _has_page("oauth-callback")


def test_every_backend_link_has_a_frontend_page_except_the_listed_gaps():
    missing = {path for path in _linked_paths() if not _has_page(path)}
    assert missing == KNOWN_MISSING_PAGES, f"unexpected missing pages: {sorted(missing - KNOWN_MISSING_PAGES)}; fixed pages to remove from the list: {sorted(KNOWN_MISSING_PAGES - missing)}"
