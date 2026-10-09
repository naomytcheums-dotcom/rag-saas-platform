"""SADM-005: platform financial writes (plan catalogue, subscription plan/status/period, refund, provider sync) are superadmin-only.

A platform admin used to grant any plan for free and extend periods without payment. Reads stay open to admins; the organization's own
self-service billing (subscribe, cancel, reactivate under `billing:manage`) is not part of this gate and keeps its own tests.
"""

import uuid

import pytest
from sqlalchemy import func, select

from api.models.admin import Plan, Subscription
from api.models.audit_log import AuditLog
from api.models.user import UserRole
from api.services import admin_subscriptions
from test_document_idor import make_tenants
from test_p1_backoffice_and_suspension import _bearer, _platform_user


async def _world(client, db_session, monkeypatch, label):
    (headers_a, _org_a, _user_a), (headers_b, org_b, _user_b) = await make_tenants(client, db_session, monkeypatch, label)
    await admin_subscriptions.ensure_default_plans_seeded(db_session)
    pro = await db_session.scalar(select(Plan).where(Plan.key == "pro"))
    sub = await admin_subscriptions.get_or_create_subscription(db_session, org_b)
    await db_session.commit()
    admin = await _platform_user(db_session, f"admin-{label}@example.com", UserRole.admin)
    superadmin = await _platform_user(db_session, f"super-{label}@example.com", UserRole.superadmin)
    return {
        "owner_a": headers_a, "owner_b": headers_b, "admin": _bearer(admin.id), "super": _bearer(superadmin.id),
        "sub_id": sub.id, "plan_before": sub.plan_id, "pro_id": pro.id,
    }


def _writes(w):
    sub, pro = w["sub_id"], w["pro_id"]
    return [
        ("PATCH", f"/admin/subscriptions/{sub}", {"plan_id": str(pro)}),
        ("PATCH", f"/admin/subscriptions/{sub}", {"status": "active"}),
        ("POST", f"/admin/subscriptions/{sub}/cancel", {"reason": "x"}),
        ("DELETE", f"/admin/subscriptions/{sub}", None),
        ("POST", f"/admin/subscriptions/{sub}/extend", {"days": 30}),
        ("POST", f"/admin/subscriptions/{sub}/refund", None),
        ("POST", "/admin/plans", {"key": "freebie", "name": "Freebie", "monthly_price_cents": 0}),
        ("PATCH", f"/admin/plans/{pro}", {"monthly_price_cents": 1}),
        ("DELETE", f"/admin/plans/{pro}", None),
        ("POST", "/admin/plans/sync/stripe-products", None),
        ("POST", "/admin/plans/sync/stripe-prices", None),
    ]


async def _snapshot(db_session, w):
    await db_session.rollback()
    sub = await db_session.scalar(select(Subscription).where(Subscription.id == w["sub_id"]).execution_options(populate_existing=True))
    pro = await db_session.scalar(select(Plan).where(Plan.id == w["pro_id"]).execution_options(populate_existing=True))
    plans = await db_session.scalar(select(func.count()).select_from(Plan))
    audits = await db_session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action.in_(["admin_subscription_changed", "admin_plan_changed"])))
    return (sub.plan_id, sub.status, sub.current_period_end, pro.monthly_price_cents, pro.is_active, plans, audits)


async def test_a_platform_admin_cannot_perform_any_financial_write(client, db_session, monkeypatch):
    w = await _world(client, db_session, monkeypatch, "sadmadmin")
    before = await _snapshot(db_session, w)
    for method, url, body in _writes(w):
        response = await client.request(method, url, json=body, headers=w["admin"])
        assert response.status_code == 403, (method, url, response.status_code, response.text)
        assert response.json()["detail"] == "Superadmin access required"
    assert await _snapshot(db_session, w) == before, "a refused write must change nothing, audit rows included"


async def test_an_organization_owner_and_an_anonymous_caller_are_refused(client, db_session, monkeypatch):
    w = await _world(client, db_session, monkeypatch, "sadmowner")
    before = await _snapshot(db_session, w)
    for method, url, body in _writes(w):
        owner = await client.request(method, url, json=body, headers=w["owner_b"])
        assert owner.status_code in (403, 404), (method, url, owner.status_code)
        anonymous = await client.request(method, url, json=body)
        assert anonymous.status_code in (401, 403), (method, url, anonymous.status_code)
    assert await _snapshot(db_session, w) == before


async def test_a_superadmin_keeps_every_write_and_each_one_is_audited(client, db_session, monkeypatch):
    w = await _world(client, db_session, monkeypatch, "sadmsuper")
    sub, pro = w["sub_id"], w["pro_id"]
    changed = await client.patch(f"/admin/subscriptions/{sub}", json={"plan_id": str(pro)}, headers=w["super"])
    extended = await client.post(f"/admin/subscriptions/{sub}/extend", json={"days": 30}, headers=w["super"])
    canceled = await client.post(f"/admin/subscriptions/{sub}/cancel", json={"reason": "support"}, headers=w["super"])
    created = await client.post("/admin/plans", json={"key": "gold", "name": "Gold", "monthly_price_cents": 5000}, headers=w["super"])
    refund = await client.post(f"/admin/subscriptions/{sub}/refund", headers=w["super"])
    assert (changed.status_code, extended.status_code, canceled.status_code, created.status_code) == (200, 200, 200, 201)
    assert refund.status_code == 501, "no processor configured: honest refusal, not a 403 and not a fake refund"
    assert (await _snapshot(db_session, w))[-1] == 4


async def test_reads_stay_open_to_a_platform_admin_but_not_to_an_ordinary_user(client, db_session, monkeypatch):
    w = await _world(client, db_session, monkeypatch, "sadmreads")
    for url in ("/admin/subscriptions", "/admin/subscriptions/stats", f"/admin/subscriptions/{w['sub_id']}", "/admin/plans"):
        assert (await client.get(url, headers=w["admin"])).status_code == 200, url
        assert (await client.get(url, headers=w["owner_b"])).status_code == 404, url


@pytest.mark.parametrize("body", [{"days": 0}, {"days": -30}, {"days": 10**9}])
async def test_extension_bounds(client, db_session, monkeypatch, body):
    w = await _world(client, db_session, monkeypatch, f"sadmdays{abs(body['days'])}")
    before = await _snapshot(db_session, w)
    response = await client.post(f"/admin/subscriptions/{w['sub_id']}/extend", json=body, headers=w["super"])
    assert response.status_code == 422
    assert await _snapshot(db_session, w) == before


async def test_plan_prices_cannot_be_negative(client, db_session, monkeypatch):
    w = await _world(client, db_session, monkeypatch, "sadmprice")
    created = await client.post("/admin/plans", json={"key": f"neg-{uuid.uuid4().hex[:6]}", "name": "Neg", "monthly_price_cents": -100}, headers=w["super"])
    updated = await client.patch(f"/admin/plans/{w['pro_id']}", json={"monthly_price_cents": -1}, headers=w["super"])
    assert (created.status_code, updated.status_code) == (422, 422)
    assert (await client.patch(f"/admin/plans/{w['pro_id']}", json={"monthly_price_cents": 0}, headers=w["super"])).status_code == 200


async def test_the_organizations_own_billing_flows_are_not_affected(client, db_session, monkeypatch):
    """The gate is on the platform back-office only: an owner still reads and cancels its own subscription."""
    (headers, org, _user), _other = await make_tenants(client, db_session, monkeypatch, "sadmown")
    assert (await client.get(f"/organizations/{org}/billing/subscription", headers=headers)).status_code == 200
    assert (await client.post(f"/organizations/{org}/billing/cancel", json={"reason": "own choice"}, headers=headers)).status_code == 200
