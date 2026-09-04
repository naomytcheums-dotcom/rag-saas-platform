"""
Partie 2.2.14 -- tests for ExternalSource CRUD, sync orchestration, and
its 5 real routes.

The real, underlying import pipelines (process_github_repo/
process_google_drive/process_notion_database/process_confluence_space/
process_onedrive) are already tested extensively elsewhere (Parties
2.1.12-2.1.18) -- mocked here at their own real call boundary (patched
on api.security.external_sources, the module that actually calls them
-- see this codebase's own established "patch where it's used, not
where a bare name was imported" lesson from Partie 2.2.7/2.2.9), since
these tests exist to prove THIS étape's own real orchestration
(dispatch by source_type, status transitions, resilience, config
encryption), not the pipelines' own internals a second time.
"""

import datetime as dt
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from api.config import settings
from api.models.external_source import ExternalSource, ExternalSourceSyncStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.external_sources import (
    create_external_source,
    decrypt_source_config,
    delete_external_source,
    detect_source_changes,
    sync_all_sources,
    sync_external_source,
    update_external_source,
)


@pytest.fixture(autouse=True)
def _ensure_secret_encryption_key(monkeypatch):
    """SECRET_ENCRYPTION_KEY is optional until a feature that needs it
    is actually used -- same real fixture already established by
    tests/test_enterprise_sso_integration.py for the exact same reason."""
    if not settings.SECRET_ENCRYPTION_KEY:
        monkeypatch.setattr(settings, "SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def _add_member(db_session, org_id, user_id, role: OrganizationRole, invited_by=None):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


async def _make_source(session, organization_id=None, source_type="github", source_id="https://github.com/acme/docs", config=None, enabled=True, last_sync_at=None) -> ExternalSource:
    from api.security.external_sources import _encrypt_config

    source = ExternalSource(
        organization_id=organization_id or uuid.uuid4(), source_type=source_type, source_id=source_id,
        config_encrypted=_encrypt_config(config), enabled=enabled, last_sync_at=last_sync_at,
    )
    session.add(source)
    await session.commit()
    return source


# ============================================================= CRUD =============================================================

async def test_create_external_source_rejects_an_unsupported_type(db_session):
    with pytest.raises(ValueError, match="source_type"):
        await create_external_source(db_session, uuid.uuid4(), None, "dropbox", "some-id", None, True, None)


async def test_create_external_source_rejects_a_workspace_from_another_organization(db_session):
    with pytest.raises(ValueError, match="workspace_id"):
        await create_external_source(db_session, uuid.uuid4(), uuid.uuid4(), "github", "https://github.com/acme/docs", None, True, None)


async def test_create_external_source_encrypts_the_real_config_at_rest(db_session):
    """Sécurité -- le config n'est jamais stocké en clair."""
    source = await create_external_source(
        db_session, uuid.uuid4(), None, "github", "https://github.com/acme/docs", {"patterns": ["*.md"]}, True, None,
    )
    assert source.config_encrypted is not None
    assert "*.md" not in source.config_encrypted  # never plaintext at rest
    assert decrypt_source_config(source) == {"patterns": ["*.md"]}


async def test_update_external_source_only_touches_fields_actually_sent(db_session):
    source = await _make_source(db_session, config={"patterns": ["*.md"]})
    updated = await update_external_source(db_session, source.id, enabled=False)
    assert updated.enabled is False
    assert decrypt_source_config(updated) == {"patterns": ["*.md"]}  # untouched


async def test_delete_external_source_removes_the_real_row(db_session):
    source = await _make_source(db_session)
    await delete_external_source(db_session, source.id)
    assert await db_session.get(ExternalSource, source.id) is None


# ================================================= detect_source_changes ==================================================

async def test_detect_source_changes_is_true_when_never_synced(db_session):
    source = await _make_source(db_session, last_sync_at=None)
    assert await detect_source_changes(source) is True


async def test_detect_source_changes_uses_the_real_github_pushed_at_signal(db_session):
    """Cohérence -- une vraie détection, pas une simple supposition,
    au moins pour GitHub."""
    last_sync = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    source = await _make_source(db_session, source_type="github", last_sync_at=last_sync)

    with patch("api.security.external_sources.fetch_github_repo", AsyncMock(return_value={"pushed_at": "2026-02-01T00:00:00Z"})):
        assert await detect_source_changes(source) is True

    with patch("api.security.external_sources.fetch_github_repo", AsyncMock(return_value={"pushed_at": "2025-12-01T00:00:00Z"})):
        assert await detect_source_changes(source) is False


async def test_detect_source_changes_falls_back_honestly_for_non_github_sources(db_session):
    """Vision critique cohérence -- limite honnête assumée pour les 4
    autres types de source."""
    recent = await _make_source(db_session, source_type="notion", last_sync_at=dt.datetime.now(dt.timezone.utc))
    assert await detect_source_changes(recent) is False  # throttled -- too recent

    old = await _make_source(db_session, source_type="notion", last_sync_at=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc))
    assert await detect_source_changes(old) is True


# ==================================================== sync_external_source ====================================================

async def test_sync_external_source_dispatches_to_the_real_github_pipeline(db_session):
    """Validation criterion: la synchronisation fonctionne."""
    source = await _make_source(db_session, source_type="github", config={"patterns": ["*.md"], "max_files": 50})

    with patch("api.security.external_sources.process_github_repo", AsyncMock(return_value="completed")) as mock_sync:
        status_value = await sync_external_source(db_session, source.id)

    assert status_value == ExternalSourceSyncStatus.idle.value
    mock_sync.assert_awaited_once_with(source.organization_id, None, source.source_id, ["*.md"], 50, None)
    await db_session.refresh(source)
    assert source.last_sync_at is not None
    assert source.sync_error is None


@pytest.mark.parametrize("source_type,patch_target", [
    ("google_drive", "process_google_drive"),
    ("notion", "process_notion_database"),
    ("confluence", "process_confluence_space"),
    ("onedrive", "process_onedrive"),
])
async def test_sync_external_source_dispatches_to_the_right_real_pipeline_per_type(db_session, source_type, patch_target):
    """Cohérence -- chaque type de source réutilise son propre vrai
    pipeline existant, jamais une logique dupliquée."""
    source = await _make_source(db_session, source_type=source_type, source_id="real-id")

    with patch(f"api.security.external_sources.{patch_target}", AsyncMock(return_value="completed")) as mock_sync:
        status_value = await sync_external_source(db_session, source.id)

    assert status_value == ExternalSourceSyncStatus.idle.value
    mock_sync.assert_awaited_once()


async def test_sync_external_source_records_a_real_failure(db_session):
    """Robustesse -- un échec réel du pipeline est journalisé, jamais
    silencieux."""
    source = await _make_source(db_session, source_type="github")

    with patch("api.security.external_sources.process_github_repo", AsyncMock(return_value="failed")):
        status_value = await sync_external_source(db_session, source.id)

    assert status_value == ExternalSourceSyncStatus.failed.value
    await db_session.refresh(source)
    assert source.sync_error is not None


async def test_sync_external_source_raises_for_a_disabled_source(db_session):
    source = await _make_source(db_session, enabled=False)
    with pytest.raises(ValueError, match="disabled"):
        await sync_external_source(db_session, source.id)


async def test_sync_all_sources_tolerates_a_real_failure_for_one_source(db_session):
    """Vision critique 2 -- une source qui échoue ne bloque pas les
    autres."""
    organization_id = uuid.uuid4()
    await _make_source(db_session, organization_id=organization_id, source_type="github", source_id="https://github.com/acme/good1")
    await _make_source(db_session, organization_id=organization_id, source_type="github", source_id="https://github.com/acme/bad")
    await _make_source(db_session, organization_id=organization_id, source_type="github", source_id="https://github.com/acme/good2")
    await _make_source(db_session, organization_id=organization_id, enabled=False)  # excluded

    async def _flaky(organization_id, workspace_id, source_id, patterns, max_files, created_by):
        if "bad" in source_id:
            raise RuntimeError("real GitHub API failure")
        return "completed"

    with patch("api.security.external_sources.process_github_repo", side_effect=_flaky):
        result = await sync_all_sources(db_session, organization_id)

    assert result == {"total": 3, "synced": 2, "failed": 1}


# ============================================================ routes ============================================================

async def test_manager_can_create_an_external_source(client, db_session, register_payload):
    """Validation criterion: la création d'une source fonctionne."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/sources", headers=_auth_header(owner_token),
        json={"source_type": "github", "source_id": "https://github.com/acme/docs", "config": {"patterns": ["*.md"]}},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "github"
    assert body["sync_status"] == "idle"
    assert "config" not in body  # write-only, never echoed back


async def test_create_external_source_rejects_an_invalid_type_via_the_route(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/sources", headers=_auth_header(owner_token),
        json={"source_type": "dropbox", "source_id": "whatever"},
    )
    assert response.status_code == 400


async def test_member_cannot_create_an_external_source(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "sourcemember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/sources", headers=_auth_header(member_token),
        json={"source_type": "github", "source_id": "https://github.com/acme/docs"},
    )
    assert response.status_code == 403


async def test_manager_can_create_an_external_source_too(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    manager_token, manager = await _register(client, db_session, "sourcemanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/sources", headers=_auth_header(manager_token),
        json={"source_type": "github", "source_id": "https://github.com/acme/docs"},
    )
    assert response.status_code == 201


async def test_manager_can_list_external_sources(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(
        f"/organizations/{org['id']}/sources", headers=_auth_header(owner_token),
        json={"source_type": "github", "source_id": "https://github.com/acme/docs"},
    )

    response = await client.get(f"/organizations/{org['id']}/sources", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_manager_can_update_an_external_source(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/sources", headers=_auth_header(owner_token),
        json={"source_type": "github", "source_id": "https://github.com/acme/docs"},
    )
    source_id = created.json()["id"]

    response = await client.patch(f"/sources/{source_id}", headers=_auth_header(owner_token), json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["enabled"] is False


async def test_member_cannot_update_an_external_source(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/sources", headers=_auth_header(owner_token),
        json={"source_type": "github", "source_id": "https://github.com/acme/docs"},
    )
    source_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "sourceupdatemember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.patch(f"/sources/{source_id}", headers=_auth_header(member_token), json={"enabled": False})
    assert response.status_code == 403


async def test_update_external_source_for_a_nonexistent_source_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.patch(f"/sources/{uuid.uuid4()}", headers=_auth_header(owner_token), json={"enabled": False})
    assert response.status_code == 404


async def test_external_source_belonging_to_another_organization_returns_404(client, db_session, register_payload):
    """Anti-énumération -- même schéma que _get_document_and_membership."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/sources", headers=_auth_header(owner_token),
        json={"source_type": "github", "source_id": "https://github.com/acme/docs"},
    )
    source_id = created.json()["id"]
    outsider_token, outsider = await _register(client, db_session, "sourceoutsider@example.com")

    response = await client.patch(f"/sources/{source_id}", headers=_auth_header(outsider_token), json={"enabled": False})
    assert response.status_code == 404


async def test_manager_can_delete_an_external_source(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/sources", headers=_auth_header(owner_token),
        json={"source_type": "github", "source_id": "https://github.com/acme/docs"},
    )
    source_id = created.json()["id"]

    response = await client.delete(f"/sources/{source_id}", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert await db_session.get(ExternalSource, uuid.UUID(source_id)) is None


async def test_manager_can_trigger_a_real_sync(client, db_session, register_payload, monkeypatch):
    """Validation criterion: la synchronisation fonctionne (via la
    route)."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/sources", headers=_auth_header(owner_token),
        json={"source_type": "github", "source_id": "https://github.com/acme/docs"},
    )
    source_id = created.json()["id"]

    monkeypatch.setattr("api.security.external_sources.process_github_repo", AsyncMock(return_value="completed"))

    response = await client.post(f"/sources/{source_id}/sync", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["sync_status"] == "idle"


async def test_member_cannot_trigger_a_sync(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/sources", headers=_auth_header(owner_token),
        json={"source_type": "github", "source_id": "https://github.com/acme/docs"},
    )
    source_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "syncmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(f"/sources/{source_id}/sync", headers=_auth_header(member_token))
    assert response.status_code == 403
