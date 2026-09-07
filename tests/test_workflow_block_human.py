"""Partie 5.4.9 -- Human workflow block. Fast SQLite suite."""

import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.workflows import create_workflow
from api.services.workflow_block_human import (
    execute_human_block, get_human_approval, list_human_blocks, render_human_message, submit_human_input,
    validate_human_input,
)
from api.services.workflow_blocks import WorkflowBlockError
from api.services.workflow_triggers import trigger_workflow


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


# --------------------------------------- render_human_message / validate_human_input --


def test_render_human_message_substitutes_real_variables():
    """Validation criterion: le rendu des messages fonctionne."""
    assert render_human_message("Approve {{amount}}?", {"amount": "$500"}) == "Approve $500?"


def test_validate_human_input_accepts_real_text():
    """Validation criterion: la validation des entrées fonctionne."""
    validate_human_input("looks good", "text")


def test_validate_human_input_rejects_empty_text():
    with pytest.raises(WorkflowBlockError):
        validate_human_input("", "text")


def test_validate_human_input_accepts_a_real_configured_select_option():
    validate_human_input("yes", "select", options=["yes", "no"])


def test_validate_human_input_rejects_an_unlisted_select_option():
    with pytest.raises(WorkflowBlockError):
        validate_human_input("maybe", "select", options=["yes", "no"])


def test_validate_human_input_accepts_a_real_bool_confirm():
    validate_human_input(True, "confirm")


def test_validate_human_input_rejects_a_non_bool_confirm():
    with pytest.raises(WorkflowBlockError):
        validate_human_input("yes", "confirm")


def test_validate_human_input_rejects_an_unknown_input_type():
    with pytest.raises(WorkflowBlockError, match="Unknown input_type"):
        validate_human_input("x", "not-real")


# --------------------------------------- execute_human_block / get_human_approval / submit_human_input --


async def test_execute_human_block_creates_a_real_pending_request(db_session):
    """Validation criterion: l'exécution du bloc Human fonctionne."""
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    run = await trigger_workflow(db_session, workflow.id, {})
    await db_session.commit()

    block = await execute_human_block(db_session, run.id, "node-1", {"message": "Approve {{amount}}?", "input_type": "confirm"}, {"amount": "$500"})
    await db_session.commit()

    assert block.status == "pending"
    assert block.message == "Approve $500?"


async def test_get_human_approval_flips_to_timeout_when_expired(db_session):
    """Validation criterion: robustesse -- le timeout est appliqué."""
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    run = await trigger_workflow(db_session, workflow.id, {})
    await db_session.commit()
    block = await execute_human_block(db_session, run.id, "node-1", {"message": "hi", "timeout": 1}, {})
    block.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    await db_session.commit()

    resolved = await get_human_approval(db_session, block.id)
    assert resolved.status == "timeout"


async def test_submit_human_input_works_for_a_real_pending_request(db_session):
    """Validation criterion: la soumission fonctionne."""
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    run = await trigger_workflow(db_session, workflow.id, {})
    await db_session.commit()
    block = await execute_human_block(db_session, run.id, "node-1", {"message": "hi", "input_type": "text"}, {})
    await db_session.commit()

    user_id = uuid.uuid4()
    updated = await submit_human_input(db_session, block.id, user_id, "approved")
    await db_session.commit()

    assert updated.status == "submitted"
    assert updated.value == "approved"
    assert updated.submitted_by == user_id


async def test_submit_human_input_rejects_an_invalid_value(db_session):
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    run = await trigger_workflow(db_session, workflow.id, {})
    await db_session.commit()
    block = await execute_human_block(db_session, run.id, "node-1", {"message": "hi", "input_type": "confirm"}, {})
    await db_session.commit()

    with pytest.raises(WorkflowBlockError):
        await submit_human_input(db_session, block.id, uuid.uuid4(), "not-a-bool")


async def test_submit_human_input_is_a_real_no_op_when_already_submitted(db_session):
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    run = await trigger_workflow(db_session, workflow.id, {})
    await db_session.commit()
    block = await execute_human_block(db_session, run.id, "node-1", {"message": "hi", "input_type": "text"}, {})
    await db_session.commit()
    await submit_human_input(db_session, block.id, uuid.uuid4(), "first")
    await db_session.commit()

    result = await submit_human_input(db_session, block.id, uuid.uuid4(), "second")
    assert result is None


async def test_list_human_blocks_orders_by_creation(db_session):
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    run = await trigger_workflow(db_session, workflow.id, {})
    await db_session.commit()
    first = await execute_human_block(db_session, run.id, "node-1", {"message": "a"}, {})
    await db_session.commit()
    second = await execute_human_block(db_session, run.id, "node-2", {"message": "b"}, {})
    await db_session.commit()

    blocks = await list_human_blocks(db_session, run.id)
    assert [b.id for b in blocks] == [first.id, second.id]


# --------------------------------------- endpoints --


async def test_manager_can_submit_a_human_block(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]
    run_response = await client.post(f"/workflows/{workflow_id}/run", json={"input": {}}, headers=_auth_header(owner_token))
    run_id = run_response.json()["id"]

    block = await execute_human_block(db_session, uuid.UUID(run_id), "node-1", {"message": "confirm?", "input_type": "confirm"}, {})
    await db_session.commit()

    response = await client.post(
        f"/workflows/runs/{run_id}/human-blocks/{block.id}/submit", json={"value": True}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "submitted"


async def test_non_member_cannot_access_human_blocks(client, db_session, register_payload):
    """Validation criterion: sécurité -- les entrées humaines sont protégées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]
    run_response = await client.post(f"/workflows/{workflow_id}/run", json={"input": {}}, headers=_auth_header(owner_token))
    run_id = run_response.json()["id"]

    other_token, other = await _register(client, db_session, "other@example.com")
    response = await client.get(f"/workflows/runs/{run_id}/human-blocks", headers=_auth_header(other_token))
    assert response.status_code == 404


async def test_get_human_block_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]
    run_response = await client.post(f"/workflows/{workflow_id}/run", json={"input": {}}, headers=_auth_header(owner_token))
    run_id = run_response.json()["id"]
    block = await execute_human_block(db_session, uuid.UUID(run_id), "node-1", {"message": "hi"}, {})
    await db_session.commit()

    response = await client.get(f"/workflows/runs/{run_id}/human-blocks/{block.id}", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["message"] == "hi"


async def test_submit_human_block_endpoint_rejects_an_invalid_value(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]
    run_response = await client.post(f"/workflows/{workflow_id}/run", json={"input": {}}, headers=_auth_header(owner_token))
    run_id = run_response.json()["id"]
    block = await execute_human_block(db_session, uuid.UUID(run_id), "node-1", {"message": "hi", "input_type": "confirm"}, {})
    await db_session.commit()

    response = await client.post(
        f"/workflows/runs/{run_id}/human-blocks/{block.id}/submit", json={"value": "not-a-bool"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400
