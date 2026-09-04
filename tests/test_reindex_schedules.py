"""
Partie 2.2.15 -- tests for ReindexSchedule CRUD, real cron evaluation,
scheduling orchestration, and its 4 routes.

reindex_organization/reindex_document (Partie 2.2.9) are already
tested extensively elsewhere -- mocked here at their own real call
boundary (patched on api.security.reindex_schedules, the module that
actually calls them), since these tests exist to prove THIS étape's
own real scheduling logic, not the reindex pipeline's own internals a
second time.
"""

import datetime as dt
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from api.models.document import Document, DocumentStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.reindex_schedule import ReindexSchedule
from api.models.user import User
from api.security.reindex_schedules import (
    check_scheduled_document_reindexes,
    check_scheduled_reindexes,
    create_reindex_schedule,
    delete_reindex_schedule,
    run_scheduled_reindexes,
    schedule_reindex,
    update_reindex_schedule,
)


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


async def _make_schedule(session, organization_id=None, cron_pattern="* * * * *", enabled=True, last_run_at=None) -> ReindexSchedule:
    schedule = ReindexSchedule(
        organization_id=organization_id or uuid.uuid4(), schedule_name="nightly", cron_pattern=cron_pattern,
        enabled=enabled, last_run_at=last_run_at,
    )
    session.add(schedule)
    await session.commit()
    return schedule


async def _make_document(session, organization_id=None, reindex_schedule=None, indexing_started_at=None, deleted_at=None) -> Document:
    document = Document(
        organization_id=organization_id or uuid.uuid4(), name="a.pdf", file_key="k", file_size=1, file_type="application/pdf",
        status=DocumentStatus.completed.value, reindex_schedule=reindex_schedule, indexing_started_at=indexing_started_at, deleted_at=deleted_at,
    )
    session.add(document)
    await session.commit()
    return document


# ============================================================= CRUD =============================================================

async def test_create_reindex_schedule_rejects_a_real_malformed_cron_pattern(db_session):
    with pytest.raises(ValueError, match="cron_pattern"):
        await create_reindex_schedule(db_session, uuid.uuid4(), "nightly", "not a cron", True)


async def test_create_reindex_schedule_computes_a_real_next_run_at(db_session):
    schedule = await create_reindex_schedule(db_session, uuid.uuid4(), "nightly", "0 2 * * *", True)
    assert schedule.next_run_at is not None


async def test_create_disabled_reindex_schedule_has_no_next_run_at(db_session):
    schedule = await create_reindex_schedule(db_session, uuid.uuid4(), "nightly", "0 2 * * *", False)
    assert schedule.next_run_at is None


async def test_update_reindex_schedule_only_touches_fields_actually_sent(db_session):
    schedule = await _make_schedule(db_session, cron_pattern="0 2 * * *")
    updated = await update_reindex_schedule(db_session, schedule.id, enabled=False)
    assert updated.enabled is False
    assert updated.cron_pattern == "0 2 * * *"  # untouched


async def test_delete_reindex_schedule_removes_the_real_row(db_session):
    schedule = await _make_schedule(db_session)
    await delete_reindex_schedule(db_session, schedule.id)
    assert await db_session.get(ReindexSchedule, schedule.id) is None


# ================================================= check_scheduled_reindexes ==================================================

async def test_check_scheduled_reindexes_finds_a_real_due_schedule(db_session):
    """Validation criterion: la planification est vérifiée
    correctement."""
    due = await _make_schedule(db_session, cron_pattern="* * * * *", last_run_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5))
    await _make_schedule(db_session, cron_pattern="0 0 1 1 *", last_run_at=dt.datetime.now(dt.timezone.utc))  # not due (once a year)

    result = await check_scheduled_reindexes(db_session)
    assert {s.id for s in result} == {due.id}


async def test_check_scheduled_reindexes_ignores_disabled_schedules(db_session):
    await _make_schedule(db_session, cron_pattern="* * * * *", enabled=False)
    assert await check_scheduled_reindexes(db_session) == []


async def test_check_scheduled_document_reindexes_finds_a_real_due_document(db_session):
    due = await _make_document(db_session, reindex_schedule="* * * * *", indexing_started_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5))
    await _make_document(db_session, reindex_schedule=None)  # no schedule at all

    result = await check_scheduled_document_reindexes(db_session)
    assert {d.id for d in result} == {due.id}


async def test_check_scheduled_document_reindexes_excludes_soft_deleted_documents(db_session):
    await _make_document(
        db_session, reindex_schedule="* * * * *", indexing_started_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5),
        deleted_at=dt.datetime.now(dt.timezone.utc),
    )
    assert await check_scheduled_document_reindexes(db_session) == []


# ========================================================= schedule_reindex ==========================================================

async def test_schedule_reindex_runs_the_real_reindex_organization_pipeline(db_session):
    schedule = await _make_schedule(db_session, cron_pattern="0 2 * * *")

    with patch("api.security.reindex_schedules.reindex_organization", AsyncMock(return_value=5)) as mock_reindex:
        scheduled_count = await schedule_reindex(db_session, schedule.id)

    assert scheduled_count == 5
    mock_reindex.assert_awaited_once_with(db_session, schedule.organization_id, triggered_by=None)
    await db_session.refresh(schedule)
    assert schedule.last_run_at is not None
    assert schedule.next_run_at is not None


# ======================================================= run_scheduled_reindexes ========================================================

async def test_run_scheduled_reindexes_tolerates_a_real_failure_for_one_schedule(db_session):
    """Vision critique 3 -- une réindexation qui échoue ne bloque pas
    les autres."""
    good = await _make_schedule(db_session, cron_pattern="* * * * *", last_run_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5))
    bad = await _make_schedule(db_session, cron_pattern="* * * * *", last_run_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5))

    async def _flaky(db, organization_id, triggered_by=None):
        if organization_id == bad.organization_id:
            raise RuntimeError("real failure")
        return 3

    with patch("api.security.reindex_schedules.reindex_organization", side_effect=_flaky):
        result = await run_scheduled_reindexes(db_session)

    assert result == {"ran": 1, "failed": 1}
    await db_session.refresh(good)
    assert good.last_run_at is not None  # the real, successful one still recorded its own run


async def test_run_scheduled_reindexes_also_runs_due_per_document_schedules(db_session):
    document = await _make_document(db_session, reindex_schedule="* * * * *", indexing_started_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5))

    with patch("api.security.reindex_schedules.reindex_document", AsyncMock(return_value=DocumentStatus.completed.value)) as mock_reindex:
        result = await run_scheduled_reindexes(db_session)

    assert result == {"ran": 1, "failed": 0}
    mock_reindex.assert_awaited_once_with(db_session, document.id, triggered_by=None)


# ============================================================ routes ============================================================

async def test_admin_can_create_a_reindex_schedule(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/reindex-schedules", headers=_auth_header(owner_token),
        json={"schedule_name": "nightly", "cron_pattern": "0 2 * * *"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["schedule_name"] == "nightly"
    assert body["next_run_at"] is not None


async def test_create_reindex_schedule_rejects_a_bad_cron_via_the_route(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/reindex-schedules", headers=_auth_header(owner_token),
        json={"schedule_name": "nightly", "cron_pattern": "garbage"},
    )
    assert response.status_code == 400


async def test_manager_cannot_create_a_reindex_schedule(client, db_session, register_payload):
    """Admin+ requis -- plus strict que Manager+ des sources
    externes (2.2.14)."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    manager_token, manager = await _register(client, db_session, "schedulemanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/reindex-schedules", headers=_auth_header(manager_token),
        json={"schedule_name": "nightly", "cron_pattern": "0 2 * * *"},
    )
    assert response.status_code == 403


async def test_admin_can_list_reindex_schedules(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(
        f"/organizations/{org['id']}/reindex-schedules", headers=_auth_header(owner_token),
        json={"schedule_name": "nightly", "cron_pattern": "0 2 * * *"},
    )

    response = await client.get(f"/organizations/{org['id']}/reindex-schedules", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_admin_can_update_a_reindex_schedule(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/reindex-schedules", headers=_auth_header(owner_token),
        json={"schedule_name": "nightly", "cron_pattern": "0 2 * * *"},
    )
    schedule_id = created.json()["id"]

    response = await client.patch(f"/reindex-schedules/{schedule_id}", headers=_auth_header(owner_token), json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["next_run_at"] is None


async def test_reindex_schedule_belonging_to_another_organization_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/reindex-schedules", headers=_auth_header(owner_token),
        json={"schedule_name": "nightly", "cron_pattern": "0 2 * * *"},
    )
    schedule_id = created.json()["id"]
    outsider_token, outsider = await _register(client, db_session, "scheduleoutsider@example.com")

    response = await client.patch(f"/reindex-schedules/{schedule_id}", headers=_auth_header(outsider_token), json={"enabled": False})
    assert response.status_code == 404


async def test_admin_can_delete_a_reindex_schedule(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/reindex-schedules", headers=_auth_header(owner_token),
        json={"schedule_name": "nightly", "cron_pattern": "0 2 * * *"},
    )
    schedule_id = created.json()["id"]

    response = await client.delete(f"/reindex-schedules/{schedule_id}", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert await db_session.get(ReindexSchedule, uuid.UUID(schedule_id)) is None
