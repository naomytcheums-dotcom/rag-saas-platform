"""Phase 5, Étape 4 -- notifications (in-app + email), built from
scratch (audit found nothing pre-existing beyond an unrelated Twilio
SMS router that happens to share the word "notifications"). Covers the
core service (preferences, creation, read/unread, multi-tenant
isolation), the 5 real triggers this étape wires (job, workflow,
billing, invitation, security), and template rendering."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from api.models.notification import Notification, NotificationPreference
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User
from api.services.notification_templates import render_notification
from api.services.notifications import (
    NotificationNotFoundError, create_notification, get_org_owner_user_id, get_unread_count, get_preferences,
    list_notifications, mark_all_read, mark_read, resolve_preference, update_preference,
)


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register_and_create_org(client, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Notif Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id


async def _make_user_and_org(db_session, email: str) -> tuple[uuid.UUID, uuid.UUID]:
    from api.security.hashing import hash_password

    user = User(email=email, hashed_password=hash_password("correct-horse-battery-staple"))
    org = Organization(name="Notif Test Org", slug=f"notif-org-{uuid.uuid4().hex[:8]}")
    db_session.add_all([user, org])
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=OrganizationRole.owner))
    await db_session.commit()
    return user.id, org.id


# -- templates ----------------------------------------------------------------

def test_render_notification_escapes_untrusted_context():
    rendered = render_notification("job_failed", {"document_name": "<script>alert(1)</script>", "error": None})
    assert "<script>" not in rendered["body"]
    assert "&lt;script&gt;" in rendered["body"]


def test_render_notification_falls_back_to_generic_for_unknown_type():
    rendered = render_notification("some_future_type_nobody_wrote_a_template_for", {"title": "Hi", "body": "Hello there"})
    assert rendered["title"] == "Hi"
    assert rendered["body"] == "Hello there"


# -- preferences ----------------------------------------------------------------

async def test_resolve_preference_defaults_to_in_app_and_email_when_no_row_exists(db_session):
    user_id, org_id = await _make_user_and_org(db_session, "prefdefault@example.com")
    in_app, email = await resolve_preference(db_session, user_id, org_id, "job_completed")
    assert (in_app, email) == (True, True)


async def test_resolve_preference_workflow_completed_defaults_in_app_only(db_session):
    user_id, org_id = await _make_user_and_org(db_session, "prefworkflow@example.com")
    in_app, email = await resolve_preference(db_session, user_id, org_id, "workflow_completed")
    assert (in_app, email) == (True, False)


async def test_resolve_preference_org_less_type_uses_hard_default(db_session):
    user_id, _ = await _make_user_and_org(db_session, "preforgless@example.com")
    in_app, email = await resolve_preference(db_session, user_id, None, "security_login_new_device")
    assert (in_app, email) == (True, False)


async def test_update_preference_persists_and_is_read_back(db_session):
    user_id, org_id = await _make_user_and_org(db_session, "prefupdate@example.com")
    await update_preference(db_session, user_id, org_id, "job_completed", email_enabled=False)
    await db_session.commit()

    in_app, email = await resolve_preference(db_session, user_id, org_id, "job_completed")
    assert (in_app, email) == (True, False)

    prefs = await get_preferences(db_session, user_id, org_id)
    assert len(prefs) == 1 and prefs[0].notification_type == "job_completed"


# -- creation / read / unread ---------------------------------------------------

async def test_create_notification_returns_none_when_both_channels_disabled(db_session):
    user_id, org_id = await _make_user_and_org(db_session, "bothdisabled@example.com")
    await update_preference(db_session, user_id, org_id, "job_completed", in_app_enabled=False, email_enabled=False)
    await db_session.commit()

    with patch("api.services.notifications._publish_realtime", new_callable=AsyncMock):
        notification = await create_notification(db_session, organization_id=org_id, user_id=user_id, notification_type="job_completed", context={"document_name": "x.pdf", "error": None})
    assert notification is None


async def test_create_notification_persists_and_publishes_realtime(db_session):
    user_id, org_id = await _make_user_and_org(db_session, "createnotif@example.com")

    with patch("api.services.notifications._publish_realtime", new_callable=AsyncMock) as mock_publish, \
         patch("api.tasks.notifications.send_notification_email_task.delay") as mock_delay:
        notification = await create_notification(db_session, organization_id=org_id, user_id=user_id, notification_type="job_completed", context={"document_name": "report.pdf", "error": None})
        await db_session.commit()

    assert notification is not None
    assert notification.title == "Document processing completed"
    assert "report.pdf" in notification.body
    mock_publish.assert_called_once()
    mock_delay.assert_called_once_with(str(notification.id))


async def test_list_unread_count_mark_read_mark_all_read(db_session):
    user_id, org_id = await _make_user_and_org(db_session, "readflow@example.com")

    with patch("api.services.notifications._publish_realtime", new_callable=AsyncMock), patch("api.tasks.notifications.send_notification_email_task.delay"):
        n1 = await create_notification(db_session, organization_id=org_id, user_id=user_id, notification_type="job_completed", context={"document_name": "a.pdf", "error": None})
        n2 = await create_notification(db_session, organization_id=org_id, user_id=user_id, notification_type="job_completed", context={"document_name": "b.pdf", "error": None})
        await db_session.commit()

    assert await get_unread_count(db_session, user_id) == 2

    await mark_read(db_session, n1.id, user_id)
    await db_session.commit()
    assert await get_unread_count(db_session, user_id) == 1

    marked = await mark_all_read(db_session, user_id)
    await db_session.commit()
    assert marked == 1
    assert await get_unread_count(db_session, user_id) == 0

    notifications = await list_notifications(db_session, user_id)
    assert {n.id for n in notifications} == {n1.id, n2.id}


async def test_mark_read_raises_for_another_users_notification(db_session):
    user_id, org_id = await _make_user_and_org(db_session, "victim@example.com")
    other_user_id, _ = await _make_user_and_org(db_session, "attacker@example.com")

    with patch("api.services.notifications._publish_realtime", new_callable=AsyncMock), patch("api.tasks.notifications.send_notification_email_task.delay"):
        notification = await create_notification(db_session, organization_id=org_id, user_id=user_id, notification_type="job_completed", context={"document_name": "a.pdf", "error": None})
        await db_session.commit()

    with pytest.raises(NotificationNotFoundError):
        await mark_read(db_session, notification.id, other_user_id)


async def test_multi_tenant_user_a_never_sees_user_bs_notifications(db_session):
    user_a, org_a = await _make_user_and_org(db_session, "usera@example.com")
    user_b, org_b = await _make_user_and_org(db_session, "userb@example.com")

    with patch("api.services.notifications._publish_realtime", new_callable=AsyncMock), patch("api.tasks.notifications.send_notification_email_task.delay"):
        await create_notification(db_session, organization_id=org_a, user_id=user_a, notification_type="job_completed", context={"document_name": "a.pdf", "error": None})
        await create_notification(db_session, organization_id=org_b, user_id=user_b, notification_type="job_completed", context={"document_name": "b.pdf", "error": None})
        await db_session.commit()

    a_notifications = await list_notifications(db_session, user_a)
    b_notifications = await list_notifications(db_session, user_b)
    assert len(a_notifications) == 1 and len(b_notifications) == 1
    assert a_notifications[0].user_id == user_a
    assert b_notifications[0].user_id == user_b


# -- endpoints (multi-tenant + auth) --------------------------------------------

async def test_notifications_endpoint_only_returns_the_callers_own(client, db_session, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    from sqlalchemy import select

    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))

    with patch("api.services.notifications._publish_realtime", new_callable=AsyncMock), patch("api.tasks.notifications.send_notification_email_task.delay"):
        await create_notification(db_session, organization_id=uuid.UUID(org_id), user_id=user.id, notification_type="job_completed", context={"document_name": "a.pdf", "error": None})
        await db_session.commit()

    response = await client.get("/notifications", headers=_auth_header(token))
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_notifications_endpoint_requires_auth(client):
    response = await client.get("/notifications")
    assert response.status_code == 401


async def test_preferences_roundtrip_via_api(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)

    update_response = await client.patch("/notifications/preferences", params={"organization_id": org_id}, json={"notification_type": "job_completed", "email_enabled": False}, headers=_auth_header(token))
    assert update_response.status_code == 200
    assert update_response.json()["email_enabled"] is False

    get_response = await client.get("/notifications/preferences", params={"organization_id": org_id}, headers=_auth_header(token))
    assert get_response.status_code == 200
    assert any(p["notification_type"] == "job_completed" and p["email_enabled"] is False for p in get_response.json())


# -- triggers -------------------------------------------------------------------

async def test_trigger_job_failed_on_document_processing_failure(db_session):
    from api.models.document import Document, DocumentStatus
    from api.tasks.document_processing import _notify_document_outcome

    user_id, org_id = await _make_user_and_org(db_session, "jobfail@example.com")
    document = Document(organization_id=org_id, created_by=user_id, name="broken.pdf", status=DocumentStatus.failed.value, file_key="docs/broken.pdf", file_size=1024, file_type="pdf", metadata_json={"error": "boom"})
    db_session.add(document)
    await db_session.commit()

    with patch("api.services.notifications._publish_realtime", new_callable=AsyncMock), patch("api.tasks.notifications.send_notification_email_task.delay"):
        await _notify_document_outcome(db_session, document)

    notifications = await list_notifications(db_session, user_id)
    assert len(notifications) == 1
    assert notifications[0].type == "job_failed"
    assert "boom" in notifications[0].body


async def test_trigger_workflow_failed_on_workflow_run_failure(db_session):
    from api.models.workflow import Workflow
    from api.models.workflow_run import WorkflowRun, WorkflowRunStatus
    from api.tasks.workflows import _notify_workflow_outcome

    user_id, org_id = await _make_user_and_org(db_session, "workflowfail@example.com")
    workflow = Workflow(organization_id=org_id, name="My Workflow", created_by=user_id, nodes=[], edges=[])
    db_session.add(workflow)
    await db_session.flush()
    run = WorkflowRun(workflow_id=workflow.id, status=WorkflowRunStatus.failed.value, error="something broke")
    db_session.add(run)
    await db_session.commit()

    with patch("api.services.notifications._publish_realtime", new_callable=AsyncMock), patch("api.tasks.notifications.send_notification_email_task.delay"):
        await _notify_workflow_outcome(db_session, run)

    notifications = await list_notifications(db_session, user_id)
    assert len(notifications) == 1
    assert notifications[0].type == "workflow_failed"
    assert "something broke" in notifications[0].body


async def test_trigger_billing_payment_failed_notifies_org_owner(db_session):
    from api.services.notifications import notify_billing_payment_failed

    user_id, org_id = await _make_user_and_org(db_session, "billingowner@example.com")

    with patch("api.services.notifications._publish_realtime", new_callable=AsyncMock), patch("api.tasks.notifications.send_notification_email_task.delay"):
        await notify_billing_payment_failed(db_session, org_id)
        await db_session.commit()

    notifications = await list_notifications(db_session, user_id)
    assert len(notifications) == 1
    assert notifications[0].type == "billing_payment_failed"
    assert notifications[0].priority == "urgent"


async def test_get_org_owner_user_id_resolves_real_owner(db_session):
    user_id, org_id = await _make_user_and_org(db_session, "ownerlookup@example.com")
    assert await get_org_owner_user_id(db_session, org_id) == user_id


async def test_trigger_invitation_received_for_an_existing_user(client, db_session, register_payload):
    from sqlalchemy import select

    owner_token, org_id = await _register_and_create_org(client, register_payload)
    invitee_id, _ = await _make_user_and_org(db_session, "existinginvitee@example.com")

    with patch("api.services.email_branding._send"), patch("api.services.notifications._publish_realtime", new_callable=AsyncMock), patch("api.tasks.notifications.send_notification_email_task.delay"):
        response = await client.post(f"/organizations/{org_id}/invitations", json={"email": "existinginvitee@example.com", "role": "member"}, headers=_auth_header(owner_token))
    assert response.status_code == 201

    notifications = await list_notifications(db_session, invitee_id)
    assert any(n.type == "invitation_received" for n in notifications)


async def test_trigger_security_login_new_device_fires_in_app_only(client, db_session, register_payload):
    from sqlalchemy import select

    with patch("api.services.email._send"):
        await client.post("/auth/register", json=register_payload)

    with patch("api.services.email._send"), patch("api.services.notifications._publish_realtime", new_callable=AsyncMock) as mock_publish, patch("api.tasks.notifications.send_notification_email_task.delay") as mock_delay:
        # A distinct User-Agent from registration's own session forces
        # is_new_device=True (api/security/sessions.py's own check
        # matches BOTH device_info and ip_address to a prior session).
        response = await client.post(
            "/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]},
            headers={"User-Agent": "a-genuinely-different-test-device/1.0"},
        )
        assert response.status_code == 200
        user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
        notifications = await list_notifications(db_session, user.id)

    assert any(n.type == "security_login_new_device" for n in notifications)
    login_notifications = [n for n in notifications if n.type == "security_login_new_device"]
    assert login_notifications[0].channel == "in_app"
    mock_delay.assert_not_called()


# -- P1 correctif: security_password_changed / security_2fa_enabled -----------

async def test_trigger_security_password_changed_fires_in_app_only(db_session):
    from api.services.notifications import create_notification

    user_id, _ = await _make_user_and_org(db_session, "pwchanged@example.com")

    with patch("api.services.notifications._publish_realtime", new_callable=AsyncMock) as mock_publish, patch("api.tasks.notifications.send_notification_email_task.delay") as mock_delay:
        notification = await create_notification(db_session, organization_id=None, user_id=user_id, notification_type="security_password_changed", priority="high", context={})
        await db_session.commit()

    assert notification is not None
    assert notification.type == "security_password_changed"
    assert notification.channel == "in_app"
    mock_publish.assert_called_once()
    mock_delay.assert_not_called()


async def test_trigger_security_2fa_enabled_fires_in_app_only(db_session):
    from api.services.notifications import create_notification

    user_id, _ = await _make_user_and_org(db_session, "2faenabled@example.com")

    with patch("api.services.notifications._publish_realtime", new_callable=AsyncMock) as mock_publish, patch("api.tasks.notifications.send_notification_email_task.delay") as mock_delay:
        notification = await create_notification(db_session, organization_id=None, user_id=user_id, notification_type="security_2fa_enabled", priority="normal", context={})
        await db_session.commit()

    assert notification is not None
    assert notification.type == "security_2fa_enabled"
    assert notification.channel == "in_app"
    mock_publish.assert_called_once()
    mock_delay.assert_not_called()


async def test_password_change_endpoint_creates_in_app_notification(client, db_session, register_payload):
    from sqlalchemy import select

    from api.services.notifications import list_notifications

    with patch("api.services.email._send"):
        token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]

    with patch("api.services.email._send"), patch("api.services.notifications._publish_realtime", new_callable=AsyncMock), patch("api.tasks.notifications.send_notification_email_task.delay"):
        response = await client.post(
            "/account/change-password", json={"current_password": register_payload["password"], "new_password": "a-different-correct-horse-battery-1"},
            headers=_auth_header(token),
        )
    assert response.status_code == 200

    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    notifications = await list_notifications(db_session, user.id)
    assert any(n.type == "security_password_changed" for n in notifications)
