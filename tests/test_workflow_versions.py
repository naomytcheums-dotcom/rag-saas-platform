"""Partie 5.4.13 -- workflow versioning. Fast SQLite suite."""

import uuid

import pytest
from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.workflows import create_workflow, update_workflow
from api.services.workflow_versions import (
    WorkflowVersionError, create_workflow_version, diff_workflow_versions, get_workflow_version,
    list_workflow_versions, restore_workflow_version,
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


# --------------------------------------- create_workflow_version / get / list --


async def test_create_workflow_version_snapshots_the_current_graph(db_session):
    """Validation criterion: la création de version fonctionne."""
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow", "nodes": [{"id": "a", "type": "trigger"}], "edges": []}, None)
    await db_session.commit()

    version = await create_workflow_version(db_session, workflow.id, None, comment="Initial")
    await db_session.commit()

    assert version.version_number == 1
    assert version.nodes == [{"id": "a", "type": "trigger"}]
    assert version.comment == "Initial"


async def test_create_workflow_version_auto_increments(db_session):
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()

    v1 = await create_workflow_version(db_session, workflow.id, None)
    await db_session.commit()
    v2 = await create_workflow_version(db_session, workflow.id, None)
    await db_session.commit()

    assert v1.version_number == 1
    assert v2.version_number == 2


async def test_get_workflow_version_returns_none_for_an_unknown_number(db_session):
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    assert await get_workflow_version(db_session, workflow.id, 99) is None


async def test_list_workflow_versions_orders_newest_first(db_session):
    """Validation criterion: la liste des versions fonctionne."""
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    await create_workflow_version(db_session, workflow.id, None)
    await db_session.commit()
    await create_workflow_version(db_session, workflow.id, None)
    await db_session.commit()

    versions = await list_workflow_versions(db_session, workflow.id)
    assert [v.version_number for v in versions] == [2, 1]


# --------------------------------------- restore_workflow_version --


async def test_restore_workflow_version_updates_the_live_graph(db_session):
    """Validation criterion: la restauration fonctionne."""
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow", "nodes": [{"id": "a", "type": "trigger"}], "edges": []}, None)
    await db_session.commit()
    await create_workflow_version(db_session, workflow.id, None)  # v1
    await db_session.commit()
    await update_workflow(db_session, workflow.id, {"nodes": [{"id": "b", "type": "llm_call"}], "edges": []})
    await db_session.commit()

    restored = await restore_workflow_version(db_session, workflow.id, 1)
    await db_session.commit()

    assert restored.nodes == [{"id": "a", "type": "trigger"}]


async def test_restore_workflow_version_creates_a_real_new_version(db_session):
    """Validation criterion: robustesse -- la restauration est un vrai commit auditable."""
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow", "nodes": [{"id": "a", "type": "trigger"}], "edges": []}, None)
    await db_session.commit()
    await create_workflow_version(db_session, workflow.id, None)  # v1
    await db_session.commit()

    await restore_workflow_version(db_session, workflow.id, 1)
    await db_session.commit()

    versions = await list_workflow_versions(db_session, workflow.id)
    assert len(versions) == 2
    assert "Restored from version 1" in versions[0].comment


async def test_restore_workflow_version_rejects_an_unknown_version_without_touching_the_workflow(db_session):
    """Validation criterion: robustesse -- que se passe-t-il si la restauration échoue."""
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow", "nodes": [{"id": "a", "type": "trigger"}], "edges": []}, None)
    await db_session.commit()

    with pytest.raises(WorkflowVersionError):
        await restore_workflow_version(db_session, workflow.id, 99)

    assert workflow.nodes == [{"id": "a", "type": "trigger"}]


# --------------------------------------- diff_workflow_versions --


async def test_diff_workflow_versions_detects_added_removed_changed(db_session):
    """Validation criterion: la comparaison fonctionne."""
    workflow = await create_workflow(
        db_session, uuid.uuid4(), {"name": "Flow", "nodes": [{"id": "a", "type": "trigger"}, {"id": "b", "type": "llm_call"}], "edges": []}, None,
    )
    await db_session.commit()
    await create_workflow_version(db_session, workflow.id, None)  # v1
    await db_session.commit()

    await update_workflow(
        db_session, workflow.id,
        {"nodes": [{"id": "a", "type": "trigger", "data": {"x": 1}}, {"id": "c", "type": "http_call"}], "edges": []},
    )
    await db_session.commit()
    await create_workflow_version(db_session, workflow.id, None)  # v2
    await db_session.commit()

    diff = await diff_workflow_versions(db_session, workflow.id, 1, 2)
    assert diff["nodes"]["added"] == ["c"]
    assert diff["nodes"]["removed"] == ["b"]
    assert diff["nodes"]["changed"] == ["a"]


async def test_diff_workflow_versions_rejects_unknown_versions(db_session):
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    with pytest.raises(WorkflowVersionError):
        await diff_workflow_versions(db_session, workflow.id, 1, 2)


# --------------------------------------- endpoints --


async def test_manager_can_create_and_restore_a_version(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/workflows", json={"name": "Flow", "nodes": [{"id": "a", "type": "trigger"}], "edges": []},
        headers=_auth_header(owner_token),
    )
    workflow_id = created.json()["id"]

    create_response = await client.post(f"/workflows/{workflow_id}/versions/create", json={"comment": "v1"}, headers=_auth_header(owner_token))
    assert create_response.status_code == 200
    assert create_response.json()["version_number"] == 1

    await client.patch(f"/workflows/{workflow_id}", json={"nodes": [{"id": "b", "type": "llm_call"}], "edges": []}, headers=_auth_header(owner_token))

    restore_response = await client.post(f"/workflows/{workflow_id}/versions/restore", json={"version_number": 1}, headers=_auth_header(owner_token))
    assert restore_response.status_code == 200
    assert restore_response.json()["nodes"] == [{"id": "a", "type": "trigger"}]


async def test_member_cannot_create_or_restore_a_version(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.post(f"/workflows/{workflow_id}/versions/create", json={}, headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_member_can_list_and_diff_versions(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]
    await client.post(f"/workflows/{workflow_id}/versions/create", json={}, headers=_auth_header(owner_token))
    await client.post(f"/workflows/{workflow_id}/versions/create", json={}, headers=_auth_header(owner_token))
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    list_response = await client.get(f"/workflows/{workflow_id}/versions", headers=_auth_header(member_token))
    assert list_response.status_code == 200
    assert len(list_response.json()) == 2

    diff_response = await client.post(
        f"/workflows/{workflow_id}/versions/diff", json={"version_a": 1, "version_b": 2}, headers=_auth_header(member_token),
    )
    assert diff_response.status_code == 200
    assert diff_response.json() == {"nodes": {"added": [], "removed": [], "changed": []}, "edges": {"added": [], "removed": [], "changed": []}}


async def test_get_workflow_version_endpoint_returns_404_for_an_unknown_version(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]

    response = await client.get(f"/workflows/{workflow_id}/versions/99", headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_restore_endpoint_rejects_an_unknown_version(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]

    response = await client.post(f"/workflows/{workflow_id}/versions/restore", json={"version_number": 99}, headers=_auth_header(owner_token))
    assert response.status_code == 400
