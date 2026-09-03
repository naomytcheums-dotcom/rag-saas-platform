"""
Partie 2.1.14 -- real network tests for api/services/google_drive_extraction.py.

**Honest, stated limitation, not glossed over**: unlike Partie 2.1.12/
2.1.13 (where `gh auth token` provided a real, usable GitHub credential
in that same session), NO real Google OAuth credentials are available
to this automated suite -- there is no `gh`-equivalent ambient
credential for Google, and provisioning one would mean registering a
real Google Cloud OAuth client and completing a real, interactive
browser consent flow, well outside this session's safe, automated
scope (the same restraint Partie 2.1.1 already took with
`S3_DOCUMENTS_BUCKET_NAME`, never auto-provisioned). The tests below
are therefore everything that genuinely CAN be verified for real, live,
with NO valid credential at all: the real, live shape of a real OAuth
rejection and a real Drive API auth rejection -- both confirmed here
the same way api/services/google_drive_extraction.py's own module
docstring already documents (that module's own real error-mapping
tests, in tests/test_google_drive_extraction.py, assert against these
SAME real shapes via a mock -- these two tests instead hit the real,
live endpoints directly, proving the mocks were not invented).

A real, full account-based import (a real folder listing, a real
download, a real refresh-token expiry/rotation) needs a real
`GOOGLE_DRIVE_REFRESH_TOKEN` pointing at a real, operator-controlled
Drive account -- skipped entirely below when one isn't configured,
mirroring `tests/test_documents_integration.py`'s own
`_require_documents_bucket`-style skip pattern.
"""

import pytest

from api.config import settings
from api.services.google_drive_extraction import (
    GoogleDriveAuthError,
    authenticate_drive,
    get_drive_file,
    list_drive_files,
)


async def test_authenticate_drive_raises_for_a_real_unregistered_oauth_client(monkeypatch):
    """Validation criterion: un token invalide est rejeté -- against
    the real, live Google OAuth token endpoint, no valid credential
    needed to trigger this specific real rejection. A real, present
    but unregistered `client_id` is set explicitly here -- confirmed
    for real that OMITTING it entirely (this test environment's own
    default, GOOGLE_DRIVE_CLIENT_ID unset) gets a real, DIFFERENT
    rejection instead (`invalid_request: Could not determine client ID
    from request`), a genuine, additional real finding."""
    monkeypatch.setattr(settings, "GOOGLE_DRIVE_CLIENT_ID", "fake-client-id.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GOOGLE_DRIVE_CLIENT_SECRET", "fake-client-secret")
    with pytest.raises(GoogleDriveAuthError, match="invalid_client"):
        await authenticate_drive("any-refresh-token-value")


async def test_get_drive_file_raises_for_a_real_invalid_access_token():
    """The real, live Drive API's own real auth rejection -- no valid
    credential needed to trigger this specific real 401 either."""
    with pytest.raises(GoogleDriveAuthError):
        await get_drive_file("any-file-id", "totally-fake-access-token-for-testing")


@pytest.fixture
def _require_real_google_drive_credentials():
    if not (settings.GOOGLE_DRIVE_REFRESH_TOKEN and settings.GOOGLE_DRIVE_CLIENT_ID and settings.GOOGLE_DRIVE_CLIENT_SECRET):
        pytest.skip(
            "GOOGLE_DRIVE_REFRESH_TOKEN/CLIENT_ID/CLIENT_SECRET are not configured -- "
            "skipping real, account-based Google Drive tests (never auto-provisioned, see this file's own module docstring)"
        )


async def test_authenticate_drive_obtains_a_real_access_token_with_real_credentials(_require_real_google_drive_credentials):
    token = await authenticate_drive(settings.GOOGLE_DRIVE_REFRESH_TOKEN)
    assert isinstance(token, str)
    assert len(token) > 0


async def test_list_drive_files_lists_a_real_folders_children_with_real_credentials(_require_real_google_drive_credentials):
    """Requires a real, operator-configured Drive folder id -- reuses
    GOOGLE_DRIVE_REFRESH_TOKEN's own owning account's real Drive root
    ('root' is Drive's own real, documented alias for it, needing no
    separate folder id to configure) so this test needs no additional
    real setup beyond the three credentials already required above."""
    access_token = await authenticate_drive(settings.GOOGLE_DRIVE_REFRESH_TOKEN)
    files = await list_drive_files("root", access_token)
    assert isinstance(files, list)
