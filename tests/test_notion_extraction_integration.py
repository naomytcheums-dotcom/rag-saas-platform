"""
Partie 2.1.16 -- real network tests for api/services/notion_extraction.py.

Same honest limitation as Partie 2.1.14/2.1.15/2.1.17/2.1.18: no real
Notion integration token is available to this automated session --
creating one requires a real, interactive Notion workspace setup step
outside this session's safe, automated scope. What's tested below is
everything genuinely verifiable live with NO valid token at all: the
real, live shape of Notion's own auth rejection.
"""

import pytest

from api.config import settings
from api.services.notion_extraction import NotionAuthError, fetch_notion_page


async def test_fetch_notion_page_raises_for_a_real_invalid_token():
    """Validation criterion: un token invalide est rejeté -- against
    the real, live Notion API, no valid token needed to trigger this
    specific real rejection."""
    with pytest.raises(NotionAuthError):
        await fetch_notion_page("00000000000000000000000000000000", "totally-fake-token-for-testing")


@pytest.fixture
def _require_real_notion_token():
    if not settings.NOTION_API_TOKEN:
        pytest.skip("NOTION_API_TOKEN is not configured -- skipping real, account-based Notion tests (never auto-provisioned)")


async def test_fetch_notion_page_works_with_a_real_configured_token_and_page(_require_real_notion_token):
    """This would need a real, operator-configured Notion page id
    shared with the integration to actually assert anything meaningful
    -- since none is configured in this session, this stays a real,
    honest skip rather than a fabricated success."""
    pytest.skip("no real, operator-configured Notion page id is available to test against in this session")
