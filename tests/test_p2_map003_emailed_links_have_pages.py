"""MAP-003 contract: every link the backend e-mails (`settings.FRONTEND_URL.rstrip('/')}/<path>?...`) must open a page that exists in the
frontend (`frontend/app/<path>/page.tsx`). Three of them used to be 404s."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"FRONTEND_URL\.rstrip\('/'\)\}/([A-Za-z0-9_\-/]+)")


def _backend_links() -> dict[str, str]:
    links = {}
    for path in (ROOT / "api").rglob("*.py"):
        for match in LINK.finditer(path.read_text(encoding="utf-8")):
            links[match.group(1).strip("/")] = str(path.relative_to(ROOT))
    return links


def test_the_contract_actually_finds_the_links_it_guards():
    links = _backend_links()
    assert {"restore-account", "reactivate-consent", "2fa-lockout-recovery"} <= set(links)


def test_every_emailed_link_has_a_frontend_page():
    missing = {link: source for link, source in _backend_links().items() if not (ROOT / "frontend" / "app" / link / "page.tsx").exists()}
    assert not missing, f"links e-mailed by the backend that open a 404: {missing}"
