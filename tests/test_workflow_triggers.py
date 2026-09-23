"""Partie 5.4.2 -- workflow triggers. Fast SQLite suite."""

import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.workflows import create_workflow
from api.services.workflow_triggers import (
    WorkflowTriggerError, check_scheduled_triggers, create_manual_trigger, create_schedule_trigger,
    create_webhook_trigger, delete_trigger, fire_scheduled_trigger, get_trigger, get_trigger_url, list_triggers,
    trigger_workflow, verify_webhook_token,
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


# --------------------------------------- create_*_trigger --


async def test_create_webhook_trigger_generates_a_real_random_token(db_session):
    """Validation criterion: la création de trigger fonctionne."""
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()

    trigger = await create_webhook_trigger(db_session, workflow.id, {})
    await db_session.commit()

    assert trigger.type == "webhook"
    assert trigger.webhook_token is not None
    assert len(trigger.webhook_token) > 20


async def test_create_schedule_trigger_accepts_a_real_valid_cron(db_session):
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()

    trigger = await create_schedule_trigger(db_session, workflow.id, "0 2 * * *")
    await db_session.commit()

    assert trigger.type == "schedule"
    assert trigger.config == {"cron_pattern": "0 2 * * *"}


async def test_create_schedule_trigger_rejects_an_invalid_cron():
    workflow_id = uuid.uuid4()
    with pytest.raises(WorkflowTriggerError):
        await create_schedule_trigger(None, workflow_id, "not a cron")


async def test_create_manual_trigger(db_session):
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    trigger = await create_manual_trigger(db_session, workflow.id)
    await db_session.commit()
    assert trigger.type == "manual"


# --------------------------------------- get_trigger_url / verify_webhook_token --


async def test_get_trigger_url_returns_the_real_literal_path(db_session):
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    trigger = await create_webhook_trigger(db_session, workflow.id, {})
    await db_session.commit()
    assert get_trigger_url(trigger) == f"/webhooks/{trigger.id}"


async def test_get_trigger_url_rejects_a_non_webhook_trigger(db_session):
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    trigger = await create_manual_trigger(db_session, workflow.id)
    await db_session.commit()
    with pytest.raises(WorkflowTriggerError):
        get_trigger_url(trigger)


async def test_verify_webhook_token_accepts_the_real_token_and_rejects_a_wrong_one(db_session):
    """Validation criterion: sécurité -- le webhook est protégé par un vrai token."""
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    trigger = await create_webhook_trigger(db_session, workflow.id, {})
    await db_session.commit()

    assert verify_webhook_token(trigger, trigger.webhook_token) is True
    assert verify_webhook_token(trigger, "wrong-token") is False


# --------------------------------------- trigger_workflow / list/delete --


async def test_trigger_workflow_creates_a_real_pending_run(db_session):
    """Validation criterion: le déclenchement fonctionne."""
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()

    run = await trigger_workflow(db_session, workflow.id, {"foo": "bar"})
    await db_session.commit()

    assert run.status == "pending"
    assert run.input == {"foo": "bar"}


async def test_list_triggers_orders_newest_first(db_session):
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    first = await create_manual_trigger(db_session, workflow.id)
    first.created_at = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    await db_session.commit()
    second = await create_webhook_trigger(db_session, workflow.id, {})
    second.created_at = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)
    await db_session.commit()

    triggers = await list_triggers(db_session, workflow.id)
    assert [t.id for t in triggers] == [second.id, first.id]


async def test_delete_trigger_removes_it(db_session):
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    trigger = await create_manual_trigger(db_session, workflow.id)
    await db_session.commit()

    assert await delete_trigger(db_session, trigger.id) is True
    await db_session.commit()
    assert await get_trigger(db_session, trigger.id) is None


async def test_delete_trigger_returns_false_for_an_unknown_id(db_session):
    assert await delete_trigger(db_session, uuid.uuid4()) is False


# --------------------------------------- check_scheduled_triggers / fire_scheduled_trigger --


async def test_check_scheduled_triggers_finds_a_real_due_trigger(db_session):
    """Validation criterion: le balayage détecte réellement un trigger cron dû."""
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    trigger = await create_schedule_trigger(db_session, workflow.id, "* * * * *")
    trigger.created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)
    await db_session.commit()

    due = await check_scheduled_triggers(db_session)
    assert trigger.id in {t.id for t in due}


async def test_check_scheduled_triggers_ignores_a_non_schedule_trigger(db_session):
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    await create_manual_trigger(db_session, workflow.id)
    await create_webhook_trigger(db_session, workflow.id, {})
    await db_session.commit()

    assert await check_scheduled_triggers(db_session) == []


async def test_fire_scheduled_trigger_creates_a_run_and_advances_last_run_at(db_session):
    """Validation criterion: le déclenchement planifié fonctionne et n'est pas rejoué en boucle."""
    workflow = await create_workflow(db_session, uuid.uuid4(), {"name": "Flow"}, None)
    await db_session.commit()
    trigger = await create_schedule_trigger(db_session, workflow.id, "* * * * *")
    await db_session.commit()
    assert trigger.last_run_at is None

    run = await fire_scheduled_trigger(db_session, trigger.id)
    await db_session.commit()

    assert run.trigger_id == trigger.id
    assert run.status == "pending"
    await db_session.refresh(trigger)
    assert trigger.last_run_at is not None
    # Just-fired, so it is no longer due against its own new last_run_at.
    assert trigger.id not in {t.id for t in await check_scheduled_triggers(db_session)}


async def test_fire_scheduled_trigger_rejects_an_unknown_id(db_session):
    with pytest.raises(WorkflowTriggerError):
        await fire_scheduled_trigger(db_session, uuid.uuid4())


# --------------------------------------- endpoints --


async def test_manager_can_create_a_webhook_trigger(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]

    response = await client.post(
        f"/workflows/{workflow_id}/triggers", json={"type": "webhook", "config": {}}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["webhook_token"] is not None


async def test_member_cannot_create_a_trigger(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.post(
        f"/workflows/{workflow_id}/triggers", json={"type": "manual", "config": {}}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_create_trigger_endpoint_rejects_an_unknown_type(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]

    response = await client.post(
        f"/workflows/{workflow_id}/triggers", json={"type": "not-real", "config": {}}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_run_workflow_manually_endpoint(client, db_session, register_payload):
    """Validation criterion: le déclenchement manuel fonctionne."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]

    response = await client.post(f"/workflows/{workflow_id}/run", json={"input": {"x": 1}}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


async def test_run_workflow_via_webhook_endpoint(client, db_session, register_payload):
    """Validation criterion: le déclenchement via webhook fonctionne."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]
    trigger_response = await client.post(
        f"/workflows/{workflow_id}/triggers", json={"type": "webhook", "config": {}}, headers=_auth_header(owner_token),
    )
    trigger_id = trigger_response.json()["id"]
    token = trigger_response.json()["webhook_token"]

    response = await client.post(f"/webhooks/{trigger_id}", json={"input": {}}, headers={"X-Webhook-Token": token})
    assert response.status_code == 200
    assert response.json()["trigger_id"] == trigger_id


async def test_run_workflow_via_webhook_rejects_a_wrong_token(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/workflows", json={"name": "Flow"}, headers=_auth_header(owner_token))
    workflow_id = created.json()["id"]
    trigger_response = await client.post(
        f"/workflows/{workflow_id}/triggers", json={"type": "webhook", "config": {}}, headers=_auth_header(owner_token),
    )
    trigger_id = trigger_response.json()["id"]

    response = await client.post(f"/webhooks/{trigger_id}", json={"input": {}}, headers={"X-Webhook-Token": "wrong"})
    assert response.status_code == 401
