"""
Partie 2.1.18 -- real network tests for api/services/onedrive_extraction.py.

**Honest, stated limitation, the same shape as Partie 2.1.14, and
genuinely better than Partie 2.1.17's own zero-host problem**: no real
Microsoft/Azure credential is available to this automated suite (no
`az`-CLI equivalent of `gh auth token` -- confirmed, `az` itself isn't
even installed here), and provisioning one would mean registering a
real Azure AD application and completing a real, interactive browser
consent flow, outside this session's safe, automated scope. The tests
below are everything that genuinely CAN be verified for real, live,
with NO valid credential at all -- both against Microsoft's own real,
universal `common`-tenant token endpoint (a genuine, always-reachable
host, unlike Confluence's own tenant-specific one, Partie 2.1.17) and
against the live Graph API's own real auth rejection.

**A real, honest finding surfaced while writing these tests, worth
stating explicitly**: unlike Google's own OAuth endpoint (Partie
2.1.14), where a missing `client_id` and an unregistered-but-present
one give two cleanly, INDEPENDENTLY REPRODUCIBLE real shapes, this same
byte-for-byte request against Microsoft's real token endpoint was
observed, live, to return `invalid_request` (`AADSTS900144`, missing
`client_id`) on one occasion and `invalid_grant` (`AADSTS9002313`,
malformed grant) on a later, otherwise identical occasion -- real
backend nondeterminism (almost certainly load-balanced across multiple
backend instances/versions), not a stable, documented distinction the
way Google's own pair is. The test below therefore only asserts that
SOME real 400 with an `error`/`error_description` shape is mapped to a
real, distinguishable `OneDriveAuthError` -- never a specific AADSTS
code, since asserting one would make this test genuinely, unfixably
flaky against the real, live endpoint.

A real, full account-based import (a real folder listing, a real
download, a real refresh-token expiry/rotation) needs a real
`ONEDRIVE_REFRESH_TOKEN` pointing at a real, operator-controlled
Microsoft 365/OneDrive account -- skipped entirely below when one isn't
configured, mirroring `tests/test_google_drive_extraction_integration.py`'s
own skip pattern.
"""

import pytest

from api.config import settings
from api.services.onedrive_extraction import OneDriveAuthError, authenticate_onedrive, get_onedrive_file, list_onedrive_files


async def test_authenticate_onedrive_raises_for_a_real_malformed_request(monkeypatch):
    """Validation criterion: un token invalide est rejeté -- against
    the real, live Microsoft identity platform `common`-tenant token
    endpoint, no valid credential needed. Deliberately does NOT assert
    which specific real AADSTS code comes back -- see this file's own
    module docstring for why that would make this test flaky."""
    monkeypatch.setattr(settings, "ONEDRIVE_CLIENT_ID", None)
    monkeypatch.setattr(settings, "ONEDRIVE_CLIENT_SECRET", None)
    with pytest.raises(OneDriveAuthError, match="Microsoft OAuth token refresh failed"):
        await authenticate_onedrive("fake")


async def test_get_onedrive_file_raises_for_a_real_invalid_access_token():
    """The real, live Graph API's own real auth rejection -- no valid
    credential needed to trigger this specific real 401 either."""
    with pytest.raises(OneDriveAuthError):
        await get_onedrive_file("any-item-id", "totally-fake-access-token-for-testing")


@pytest.fixture
def _require_real_onedrive_credentials():
    if not (settings.ONEDRIVE_REFRESH_TOKEN and settings.ONEDRIVE_CLIENT_ID and settings.ONEDRIVE_CLIENT_SECRET):
        pytest.skip(
            "ONEDRIVE_REFRESH_TOKEN/CLIENT_ID/CLIENT_SECRET are not configured -- "
            "skipping real, account-based OneDrive tests (never auto-provisioned, see this file's own module docstring)"
        )


async def test_authenticate_onedrive_obtains_a_real_access_token_with_real_credentials(_require_real_onedrive_credentials):
    token = await authenticate_onedrive(settings.ONEDRIVE_REFRESH_TOKEN)
    assert isinstance(token, str)
    assert len(token) > 0


async def test_list_onedrive_files_lists_a_real_folders_children_with_real_credentials(_require_real_onedrive_credentials):
    """Requires no additional real setup beyond the three credentials
    already required above -- `root` is Graph's own real, documented
    alias for the owning account's own OneDrive root folder."""
    access_token = await authenticate_onedrive(settings.ONEDRIVE_REFRESH_TOKEN)
    files = await list_onedrive_files("root", access_token)
    assert isinstance(files, list)
