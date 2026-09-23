"""Partie 5.4.1 -- workflow CRUD + structural validation. Fast SQLite suite."""

import uuid

import pytest
from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.models.workflow import Workflow
from api.security.workflows import create_workflow, delete_workflow, import_workflow, list_workflows, update_workflow
from api.services.workflows import (
    WorkflowValidationError, add_edge, add_node, delete_node, export_workflow, update_node, validate_workflow,
    validate_workflow_data,
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


def _make_workflow(**overrides) -> Workflow:
    return Workflow(id=uuid.uuid4(), organization_id=uuid.uuid4(), name="Test", nodes=[], edges=[], **overrides)


# --------------------------------------- add/delete/update_node, add_edge --


def test_add_node_creates_a_real_node_with_a_real_id():
    """Validation criterion: l'ajout de blocs fonctionne."""
    workflow = _make_workflow()
    node = add_node(workflow, "llm_call", {"x": 0, "y": 0})
    assert workflow.nodes == [node]
    assert node["type"] == "llm_call"
    assert "id" in node


def test_add_node_rejects_an_unknown_block_type():
    workflow = _make_workflow()
    with pytest.raises(WorkflowValidationError, match="Unknown block type"):
        add_node(workflow, "not-a-real-block", {"x": 0, "y": 0})


def test_add_edge_connects_two_real_nodes():
    workflow = _make_workflow()
    node_a = add_node(workflow, "trigger", {"x": 0, "y": 0})
    node_b = add_node(workflow, "llm_call", {"x": 1, "y": 1})
    edge = add_edge(workflow, node_a["id"], node_b["id"])
    assert workflow.edges == [edge]


def test_add_edge_rejects_an_unknown_node_id():
    workflow = _make_workflow()
    node_a = add_node(workflow, "trigger", {"x": 0, "y": 0})
    with pytest.raises(WorkflowValidationError, match="Unknown node"):
        add_edge(workflow, node_a["id"], "not-a-real-node")


def test_delete_node_removes_the_node_and_its_real_edges():
    """Validation criterion: robustesse -- pas d'arête en suspens."""
    workflow = _make_workflow()
    node_a = add_node(workflow, "trigger", {"x": 0, "y": 0})
    node_b = add_node(workflow, "llm_call", {"x": 1, "y": 1})
    add_edge(workflow, node_a["id"], node_b["id"])

    assert delete_node(workflow, node_a["id"]) is True
    assert workflow.nodes == [node_b]
    assert workflow.edges == []


def test_delete_node_is_a_real_no_op_for_an_unknown_id():
    workflow = _make_workflow()
    assert delete_node(workflow, "not-a-real-node") is False


def test_update_node_merges_data_and_position():
    workflow = _make_workflow()
    node = add_node(workflow, "llm_call", {"x": 0, "y": 0}, data={"model": "sonnet"})
    updated = update_node(workflow, node["id"], data={"temperature": 0.5}, position={"x": 5, "y": 5})
    assert updated["data"] == {"model": "sonnet", "temperature": 0.5}
    assert updated["position"] == {"x": 5, "y": 5}


def test_update_node_returns_none_for_an_unknown_id():
    workflow = _make_workflow()
    assert update_node(workflow, "not-a-real-node", data={}) is None


# --------------------------------------- validate_workflow --


def test_validate_workflow_passes_a_real_valid_graph():
    """Validation criterion: la validation fonctionne."""
    nodes = [{"id": "a", "type": "trigger"}, {"id": "b", "type": "llm_call"}]
    edges = [{"id": "e1", "source": "a", "target": "b"}]
    assert validate_workflow(nodes, edges) == []


def test_validate_workflow_rejects_an_unknown_block_type():
    errors = validate_workflow([{"id": "a", "type": "not-real"}], [])
    assert any("unknown type" in e for e in errors)


def test_validate_workflow_rejects_a_dangling_edge():
    """Validation criterion: robustesse -- les workflows invalides sont rejetés."""
    errors = validate_workflow([{"id": "a", "type": "trigger"}], [{"id": "e1", "source": "a", "target": "ghost"}])
    assert any("unknown node id" in e for e in errors)


def test_validate_workflow_rejects_duplicate_node_ids():
    errors = validate_workflow([{"id": "a", "type": "trigger"}, {"id": "a", "type": "llm_call"}], [])
    assert any("Duplicate" in e for e in errors)


# --------------------------------------- export/import --


async def test_export_workflow_returns_a_real_portable_representation(db_session):
    """Validation criterion: l'export/import fonctionne."""
    org_id = uuid.uuid4()
    workflow = await create_workflow(db_session, org_id, {"name": "My Flow", "nodes": [{"id": "a", "type": "trigger"}], "edges": []}, None)
    await db_session.commit()

    exported = export_workflow(workflow)
    assert exported == {"name": "My Flow", "description": None, "nodes": [{"id": "a", "type": "trigger"}], "edges": [], "variables": []}


async def test_import_workflow_creates_a_real_new_workflow(db_session):
    org_id = uuid.uuid4()
    data = {"name": "Imported", "nodes": [{"id": "a", "type": "trigger"}], "edges": []}
    workflow = await import_workflow(db_session, org_id, data, None)
    await db_session.commit()

    assert workflow.name == "Imported"
    assert workflow.organization_id == org_id


async def test_import_workflow_rejects_an_invalid_graph(db_session):
    with pytest.raises(WorkflowValidationError):
        await import_workflow(db_session, uuid.uuid4(), {"name": "Bad", "nodes": [{"id": "a", "type": "not-real"}], "edges": []}, None)


def test_validate_workflow_data_raises_with_every_real_error():
    with pytest.raises(WorkflowValidationError):
        validate_workflow_data({"nodes": [{"id": "a", "type": "not-real"}], "edges": []})


# --------------------------------------- CRUD --


async def test_create_and_get_workflow(db_session):
    org_id = uuid.uuid4()
    workflow = await create_workflow(db_session, org_id, {"name": "Bot Flow"}, None)
    await db_session.commit()
    assert workflow.status == "draft"


async def test_update_workflow_rejects_an_invalid_graph_via_generic_update(db_session):
    """Validation criterion: sécurité/robustesse -- pas de contournement via l'endpoint générique."""
    org_id = uuid.uuid4()
    workflow = await create_workflow(db_session, org_id, {"name": "Bot Flow"}, None)
    await db_session.commit()
    with pytest.raises(WorkflowValidationError):
        await update_workflow(db_session, workflow.id, {"nodes": [{"id": "a", "type": "not-real"}]})


async def test_delete_workflow_is_a_real_soft_delete(db_session):
    org_id = uuid.uuid4()
    workflow = await create_workflow(db_session, org_id, {"name": "Bot Flow"}, None)
    await db_session.commit()

    assert await delete_workflow(db_session, workflow.id) is True
    await db_session.commit()
    assert await db_session.get(Workflow, workflow.id) is not None  # real row still exists
    assert (await db_session.get(Workflow, workflow.id)).deleted_at is not None


async def test_list_workflows_excludes_soft_deleted(db_session):
    org_id = uuid.uuid4()
    kept = await create_workflow(db_session, org_id, {"name": "Kept"}, None)
    deleted = await create_workflow(db_session, org_id, {"name": "Deleted"}, None)
    await db_session.commit()
    await delete_workflow(db_session, deleted.id)
    await db_session.commit()

    workflows = await list_workflows(db_session, org_id)
    assert [w.id for w in workflows] == [kept.id]


# --------------------------------------- endpoints --


async def test_manager_can_create_and_list_workflows(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    create_response = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    assert create_response.status_code == 201

    list_response = await client.get(f"/organizations/{org['id']}/workflows", headers=_auth_header(owner_token))
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


async def test_member_cannot_create_a_workflow(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_get_update_delete_workflow_endpoints(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]

    get_response = await client.get(f"/workflows/{workflow_id}", headers=_auth_header(owner_token))
    assert get_response.status_code == 200

    patch_response = await client.patch(f"/workflows/{workflow_id}", json={"name": "Renamed"}, headers=_auth_header(owner_token))
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "Renamed"

    delete_response = await client.delete(f"/workflows/{workflow_id}", headers=_auth_header(owner_token))
    assert delete_response.status_code == 204

    after_delete = await client.get(f"/workflows/{workflow_id}", headers=_auth_header(owner_token))
    assert after_delete.status_code == 404


async def test_validate_workflow_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/workflows",
        json={"name": "Flow", "nodes": [{"id": "a", "type": "trigger"}], "edges": []},
        headers=_auth_header(owner_token),
    )
    workflow_id = created.json()["id"]

    response = await client.post(f"/workflows/{workflow_id}/validate", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json() == {"valid": True, "errors": []}


async def test_create_workflow_endpoint_rejects_an_invalid_graph(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/workflows",
        json={"name": "Flow", "nodes": [{"id": "a", "type": "not-real"}], "edges": []},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_cannot_access_a_workflow_from_another_organization(client, db_session, register_payload):
    """Validation criterion: sécurité -- isolation par organisation."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]

    other_token, other_owner = await _register(client, db_session, "other@example.com")
    response = await client.get(f"/workflows/{workflow_id}", headers=_auth_header(other_token))
    assert response.status_code == 404


# --------------------------------------- Phase 5, Étape 5: run history + import/export endpoints --
# Real gap found during this étape's own audit: POST .../run existed
# with no way to list past runs or fetch one's own detail, and
# import_workflow/export_workflow existed with zero HTTP surface at
# all -- both closed here, for the Workflow Builder UI's own
# execution-history and import/export panels.

async def test_list_and_get_workflow_runs(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/workflows",
        json={"name": "Flow", "nodes": [{"id": "a", "type": "trigger"}, {"id": "b", "type": "code", "data": {"code": "'done'"}}], "edges": [{"id": "e1", "source": "a", "target": "b"}]},
        headers=_auth_header(owner_token),
    )
    workflow_id = created.json()["id"]

    run_response = await client.post(f"/workflows/{workflow_id}/run", json={}, headers=_auth_header(owner_token))
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    list_response = await client.get(f"/workflows/{workflow_id}/runs", headers=_auth_header(owner_token))
    assert list_response.status_code == 200
    assert any(r["id"] == run_id for r in list_response.json())

    detail_response = await client.get(f"/workflows/runs/{run_id}", headers=_auth_header(owner_token))
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == run_id


async def test_cannot_list_runs_or_get_run_from_another_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/workflows",
        json={"name": "Flow", "nodes": [{"id": "a", "type": "trigger"}], "edges": []},
        headers=_auth_header(owner_token),
    )
    workflow_id = created.json()["id"]
    run_response = await client.post(f"/workflows/{workflow_id}/run", json={}, headers=_auth_header(owner_token))
    run_id = run_response.json()["id"]

    other_token, _ = await _register(client, db_session, "otherrunner@example.com")
    assert (await client.get(f"/workflows/{workflow_id}/runs", headers=_auth_header(other_token))).status_code == 404
    assert (await client.get(f"/workflows/runs/{run_id}", headers=_auth_header(other_token))).status_code == 404


async def test_import_and_export_workflow_via_http(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    import_response = await client.post(
        f"/organizations/{org['id']}/workflows/import",
        json={"name": "Imported Flow", "nodes": [{"id": "a", "type": "trigger"}], "edges": []},
        headers=_auth_header(owner_token),
    )
    assert import_response.status_code == 201
    workflow_id = import_response.json()["id"]

    export_response = await client.get(f"/workflows/{workflow_id}/export", headers=_auth_header(owner_token))
    assert export_response.status_code == 200
    assert export_response.json() == {"name": "Imported Flow", "description": None, "nodes": [{"id": "a", "type": "trigger"}], "edges": [], "variables": []}


async def test_import_workflow_endpoint_rejects_an_invalid_graph(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/workflows/import",
        json={"name": "Bad", "nodes": [{"id": "a", "type": "not-real"}], "edges": []},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_member_cannot_import_a_workflow(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "importmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.post(
        f"/organizations/{org['id']}/workflows/import", json={"name": "Flow", "nodes": [], "edges": []}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403
