"""P1 back-office (TEN-002 / SADM-004 suspension, SADM-002 rank rules, SADM-003 organization deletion, SADM-005 audit + validation).

Before: suspending an organization only wrote a flag nothing read, a platform admin could suspend or rename a superadmin (or
themselves), DELETE /admin/organizations/{id} answered 500 (the audit row pointed at the organization deleted in the same
transaction), and manual plan/status changes left no trace."""

import datetime as dt
import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from api.models.admin import Subscription
from api.models.agent import Agent
from api.models.audit_log import AuditLog
from api.models.document import Document
from api.models.media import MediaAsset, MediaStatus, MediaType
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User, UserRole
from api.security.jwt import create_access_token
from api.services.organization_api_keys import generate_organization_api_key
from api.config import settings
from test_document_idor import make_tenants


def _bearer(user_id) -> dict:
    token, _ = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


async def _platform_user(db_session, email, role):
    user = User(
        email=email, hashed_password="unused", is_email_verified=True, role=role,
        terms_version=settings.TERMS_VERSION, consent_given_at=dt.datetime.now(dt.timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _world(client, db_session, monkeypatch, label):
    (headers_a, org_a, user_a), (headers_b, org_b, user_b) = await make_tenants(client, db_session, monkeypatch, label)
    document = Document(organization_id=org_b, created_by=user_b, name="b.txt", file_key="k", file_size=1, file_type="text/plain", status="completed")
    agent = Agent(organization_id=org_b, name="B agent", system_prompt="x")
    media = MediaAsset(
        organization_id=org_b, uploaded_by=user_b, media_type=MediaType.video, status=MediaStatus.completed, filename="v.mp4",
        file_key="media/k", file_size=1, mime_type="video/mp4",
    )
    db_session.add_all([document, agent, media])
    await db_session.commit()
    _key_row, api_key = await generate_organization_api_key(db_session, org_b, "key-b", ["kb:read", "kb:write"])
    await db_session.commit()
    superadmin = await _platform_user(db_session, f"super-{label}@example.com", UserRole.superadmin)
    return {
        "headers_a": headers_a, "org_a": org_a, "headers_b": headers_b, "org_b": org_b, "user_b": user_b,
        "document": document.id, "agent": agent.id, "media": media.id, "api_key": api_key, "super": _bearer(superadmin.id),
    }


# ------------------------------------------------------------ TEN-002 / SADM-004


async def test_a_suspended_organization_is_cut_off_on_every_access_path(client, db_session, monkeypatch):
    w = await _world(client, db_session, monkeypatch, "susp")
    probes = [
        ("GET", f"/organizations/{w['org_b']}/documents"),
        ("GET", f"/organizations/{w['org_b']}/agents"),
        ("POST", f"/organizations/{w['org_b']}/agents"),
        ("GET", f"/documents/{w['document']}"),
        ("GET", f"/agents/{w['agent']}"),
        ("GET", f"/media/{w['media']}"),
    ]
    body = {"POST": {"name": "n", "system_prompt": "p"}}
    for method, url in probes:  # control: everything answers normally before the suspension
        response = await client.request(method, url, json=body.get(method), headers=w["headers_b"])
        assert response.status_code != 403, (method, url, response.text)
    key_before = await client.get("/v1/knowledge-bases", headers={"X-API-Key": w["api_key"]})
    assert key_before.status_code == 200

    suspended = await client.post(f"/admin/organizations/{w['org_b']}/suspend", json={"reason": "abuse"}, headers=w["super"])
    assert suspended.status_code == 200 and suspended.json()["is_suspended"] is True

    for method, url in probes:
        response = await client.request(method, url, json=body.get(method), headers=w["headers_b"])
        assert response.status_code == 403, (method, url, response.status_code, response.text)
        assert response.json()["detail"] == "This organization is suspended"
    key_after = await client.get("/v1/knowledge-bases", headers={"X-API-Key": w["api_key"]})
    assert key_after.status_code == 403


async def test_suspension_does_not_touch_other_organizations_or_hide_the_organization_from_non_members(client, db_session, monkeypatch):
    w = await _world(client, db_session, monkeypatch, "susp2")
    await client.post(f"/admin/organizations/{w['org_b']}/suspend", json={"reason": "abuse"}, headers=w["super"])

    own = await client.get(f"/organizations/{w['org_a']}/documents", headers=w["headers_a"])
    probe = await client.get(f"/organizations/{w['org_b']}/documents", headers=w["headers_a"])

    assert own.status_code == 200
    assert probe.status_code == 404  # a non-member still learns nothing about the (suspended) organization


async def test_reactivating_an_organization_restores_access(client, db_session, monkeypatch):
    w = await _world(client, db_session, monkeypatch, "susp3")
    await client.post(f"/admin/organizations/{w['org_b']}/suspend", json={"reason": "unpaid"}, headers=w["super"])
    assert (await client.get(f"/organizations/{w['org_b']}/documents", headers=w["headers_b"])).status_code == 403

    activated = await client.post(f"/admin/organizations/{w['org_b']}/activate", headers=w["super"])

    assert activated.status_code == 200
    assert (await client.get(f"/organizations/{w['org_b']}/documents", headers=w["headers_b"])).status_code == 200
    assert (await client.get(f"/documents/{w['document']}", headers=w["headers_b"])).status_code == 200
    assert (await client.get("/v1/knowledge-bases", headers={"X-API-Key": w["api_key"]})).status_code == 200


# ------------------------------------------------------------ SADM-002


async def test_an_admin_cannot_act_on_a_superadmin_or_another_admin(client, db_session, monkeypatch):
    admin = await _platform_user(db_session, "admin-rank@example.com", UserRole.admin)
    other_admin = await _platform_user(db_session, "admin-two@example.com", UserRole.admin)
    superadmin = await _platform_user(db_session, "super-rank@example.com", UserRole.superadmin)
    headers = _bearer(admin.id)
    superadmin_id = superadmin.id
    for target in (superadmin, other_admin):
        suspend = await client.post(f"/admin/users/{target.id}/suspend", json={"reason": "x"}, headers=headers)
        activate = await client.post(f"/admin/users/{target.id}/activate", headers=headers)
        reset = await client.post(f"/admin/users/{target.id}/reset-password", headers=headers)
        verify = await client.post(f"/admin/users/{target.id}/verify-email", headers=headers)
        rename = await client.patch(f"/admin/users/{target.id}", json={"full_name": "Pwned"}, headers=headers)
        session = await client.delete(f"/admin/users/{target.id}/sessions/{uuid.uuid4()}", headers=headers)
        assert [r.status_code for r in (suspend, activate, reset, verify, rename, session)] == [403] * 6
    db_session.expire_all()
    reloaded = await db_session.scalar(select(User).where(User.id == superadmin_id).execution_options(populate_existing=True))
    assert reloaded.is_active is True
    assert reloaded.full_name != "Pwned"


async def test_an_admin_still_manages_ordinary_accounts(client, db_session, monkeypatch):
    admin = await _platform_user(db_session, "admin-ok@example.com", UserRole.admin)
    ordinary = await _platform_user(db_session, "ordinary@example.com", UserRole.user)
    headers = _bearer(admin.id)
    suspended = await client.post(f"/admin/users/{ordinary.id}/suspend", json={"reason": "abuse"}, headers=headers)
    activated = await client.post(f"/admin/users/{ordinary.id}/activate", headers=headers)
    renamed = await client.patch(f"/admin/users/{ordinary.id}", json={"full_name": "Renamed"}, headers=headers)
    assert (suspended.status_code, activated.status_code, renamed.status_code) == (200, 200, 200)


async def test_a_superadmin_can_act_on_admins_but_nobody_can_suspend_themselves(client, db_session, monkeypatch):
    superadmin = await _platform_user(db_session, "super-self@example.com", UserRole.superadmin)
    admin = await _platform_user(db_session, "admin-self@example.com", UserRole.admin)
    superadmin_id = superadmin.id
    headers = _bearer(superadmin_id)
    admin_id = admin.id
    assert (await client.post(f"/admin/users/{admin_id}/suspend", json={"reason": "x"}, headers=headers)).status_code == 200
    assert (await client.post(f"/admin/users/{superadmin_id}/suspend", json={"reason": "x"}, headers=headers)).status_code == 403
    own = await _platform_user(db_session, "admin-self2@example.com", UserRole.admin)
    own_id = own.id
    admin_headers = _bearer(own_id)
    assert (await client.post(f"/admin/users/{own_id}/suspend", json={"reason": "x"}, headers=admin_headers)).status_code == 403
    reloaded = await db_session.scalar(select(User).where(User.id == superadmin_id).execution_options(populate_existing=True))
    assert reloaded.is_active is True


# ------------------------------------------------------------ SADM-003


async def test_deleting_an_organization_works_keeps_its_audit_trail_and_purges_its_files(client, db_session, monkeypatch):
    w = await _world(client, db_session, monkeypatch, "del")
    deleted_keys = []
    monkeypatch.setattr("api.services.document_storage.delete_document_file", lambda key: deleted_keys.append(key))

    response = await client.delete(f"/admin/organizations/{w['org_b']}", headers=w["super"])

    assert response.status_code == 204, response.text
    db_session.expire_all()
    assert await db_session.get(Organization, w["org_b"]) is None  # (the cascade to agents/documents is a PostgreSQL FK behavior, not simulated by SQLite)
    assert sorted(deleted_keys) == ["k", "media/k"]
    trail = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "organization_deleted"))).all()
    assert len(trail) == 1 and trail[0].resource_id == str(w["org_b"]) and trail[0].organization_id is None
    assert (await client.get(f"/admin/organizations/{w['org_b']}", headers=w["super"])).status_code == 404


async def test_deleting_an_organization_cancels_its_stripe_subscription(client, db_session, monkeypatch):
    from api.services import admin_subscriptions, billing_stripe

    w = await _world(client, db_session, monkeypatch, "delstripe")
    sub = await admin_subscriptions.get_or_create_subscription(db_session, w["org_b"])
    sub.stripe_subscription_id = "sub_TO_CANCEL"
    await db_session.commit()
    fake = MagicMock()
    monkeypatch.setattr("api.services.document_storage.delete_document_file", lambda key: None)
    with patch.object(billing_stripe, "_client", return_value=fake):
        response = await client.delete(f"/admin/organizations/{w['org_b']}", headers=w["super"])
    assert response.status_code == 204
    fake.Subscription.cancel.assert_called_once_with("sub_TO_CANCEL")


async def test_a_provider_failure_does_not_block_the_deletion(client, db_session, monkeypatch):
    from api.services import admin_subscriptions, billing_stripe

    w = await _world(client, db_session, monkeypatch, "delfail")
    sub = await admin_subscriptions.get_or_create_subscription(db_session, w["org_b"])
    sub.stripe_subscription_id = "sub_X"
    await db_session.commit()
    fake = MagicMock()
    fake.Subscription.cancel.side_effect = RuntimeError("stripe down")
    monkeypatch.setattr("api.services.document_storage.delete_document_file", lambda key: None)
    with patch.object(billing_stripe, "_client", return_value=fake):
        response = await client.delete(f"/admin/organizations/{w['org_b']}", headers=w["super"])
    assert response.status_code == 204


async def test_only_a_superadmin_may_delete_an_organization(client, db_session, monkeypatch):
    w = await _world(client, db_session, monkeypatch, "delauth")
    admin = await _platform_user(db_session, "admin-del@example.com", UserRole.admin)
    assert (await client.delete(f"/admin/organizations/{w['org_b']}", headers=_bearer(admin.id))).status_code == 403
    assert (await client.delete(f"/admin/organizations/{w['org_b']}", headers=w["headers_b"])).status_code in (403, 404)
    assert (await client.delete(f"/admin/organizations/{uuid.uuid4()}", headers=w["super"])).status_code == 404


# ------------------------------------------------------------ SADM-005 (audit + validation; the superadmin gate is a pending decision)


async def test_manual_subscription_changes_are_audited_with_before_and_after(client, db_session, monkeypatch):
    from api.services import admin_subscriptions

    w = await _world(client, db_session, monkeypatch, "audit")
    await admin_subscriptions.ensure_default_plans_seeded(db_session)
    pro = await db_session.scalar(select(admin_subscriptions.Plan).where(admin_subscriptions.Plan.key == "pro"))
    sub = await admin_subscriptions.get_or_create_subscription(db_session, w["org_b"])
    await db_session.commit()
    before_plan = str(sub.plan_id)

    changed = await client.patch(f"/admin/subscriptions/{sub.id}", json={"plan_id": str(pro.id)}, headers=w["super"])
    extended = await client.post(f"/admin/subscriptions/{sub.id}/extend", json={"days": 30}, headers=w["super"])
    canceled = await client.post(f"/admin/subscriptions/{sub.id}/cancel", json={"reason": "fraud"}, headers=w["super"])

    assert (changed.status_code, extended.status_code, canceled.status_code) == (200, 200, 200)
    rows = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "admin_subscription_changed").order_by(AuditLog.timestamp, AuditLog.id))).all()
    assert sorted(json.loads(row.metadata_json)["operation"] for row in rows) == ["cancel", "extend", "update"]
    first = next(json.loads(row.metadata_json) for row in rows if json.loads(row.metadata_json)["operation"] == "update")
    assert first["before"]["plan_id"] == before_plan and first["after"]["plan_id"] == str(pro.id)


async def test_an_unknown_plan_is_a_404_not_a_500(client, db_session, monkeypatch):
    from api.services import admin_subscriptions

    w = await _world(client, db_session, monkeypatch, "plan404")
    sub = await admin_subscriptions.get_or_create_subscription(db_session, w["org_b"])
    await db_session.commit()
    sub_id, plan_id_before = sub.id, sub.plan_id
    response = await client.patch(f"/admin/subscriptions/{sub_id}", json={"plan_id": str(uuid.uuid4())}, headers=w["super"])
    assert response.status_code == 404
    unchanged = await db_session.scalar(select(Subscription).where(Subscription.id == sub_id).execution_options(populate_existing=True))
    assert unchanged.plan_id == plan_id_before


async def test_plan_catalog_changes_are_audited(client, db_session, monkeypatch):
    w = await _world(client, db_session, monkeypatch, "planaudit")
    created = await client.post("/admin/plans", json={"key": "gold", "name": "Gold", "monthly_price_cents": 5000}, headers=w["super"])
    plan_id = created.json()["id"]
    updated = await client.patch(f"/admin/plans/{plan_id}", json={"monthly_price_cents": 1}, headers=w["super"])
    removed = await client.delete(f"/admin/plans/{plan_id}", headers=w["super"])
    assert (created.status_code, updated.status_code, removed.status_code) == (201, 200, 204)
    rows = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "admin_plan_changed"))).all()
    assert len(rows) == 3
