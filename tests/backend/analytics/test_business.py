"""Partie 20 -- business metrics (revenue/customers/retention/churn/ltv),
platform-wide, superadmin-only (same real scope as
api/services/admin_subscriptions.py, which these extend rather than
duplicate)."""

import datetime as dt
import uuid

from sqlalchemy import select

from api.models.user import User, UserRole


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _make_superadmin(client, db_session, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.superadmin
    await db_session.commit()
    return token, user


async def test_business_endpoints_require_superadmin(client, db_session, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.get("/analytics/business/revenue", headers=_auth_header(token))
    assert response.status_code == 403


async def test_revenue_endpoint_reuses_real_admin_subscriptions_math(client, db_session, register_payload):
    admin_token, _admin = await _make_superadmin(client, db_session, register_payload)
    response = await client.get("/analytics/business/revenue", headers=_auth_header(admin_token))
    assert response.status_code == 200
    body = response.json()
    for key in ("mrr_cents", "arr_cents", "active_subscriptions", "arpu_cents", "churn_last_30d"):
        assert key in body


async def test_churn_rate_is_none_with_no_real_subscriptions(client, db_session, register_payload):
    admin_token, _admin = await _make_superadmin(client, db_session, register_payload)
    response = await client.get("/analytics/business/churn", headers=_auth_header(admin_token))
    assert response.status_code == 200
    assert response.json()["churn_rate"] is None


async def test_churn_rate_reflects_a_real_canceled_subscription(client, db_session, register_payload):
    from api.models.admin import Plan, Subscription, SubscriptionStatus

    admin_token, _admin = await _make_superadmin(client, db_session, register_payload)
    org = (await client.post("/organizations", json={"name": "Churned Co"}, headers=_auth_header(admin_token))).json()
    plan = Plan(key="churn-test-plan", name="Test", monthly_price_cents=1000)
    db_session.add(plan)
    await db_session.flush()
    await client.get(f"/organizations/{org['id']}/billing/subscription", headers=_auth_header(admin_token))
    sub = await db_session.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(org["id"])))
    sub.plan_id = plan.id
    sub.status = SubscriptionStatus.canceled
    sub.canceled_at = dt.datetime.now(dt.timezone.utc)
    await db_session.commit()

    response = await client.get("/analytics/business/churn", headers=_auth_header(admin_token))
    body = response.json()
    assert body["canceled"] >= 1
    assert body["churn_rate"] is not None
    assert 0 < body["churn_rate"] <= 1


async def test_ltv_is_none_without_a_real_churn_signal(client, db_session, register_payload):
    admin_token, _admin = await _make_superadmin(client, db_session, register_payload)
    response = await client.get("/analytics/business/ltv", headers=_auth_header(admin_token))
    assert response.status_code == 200
    assert response.json()["ltv_cents"] is None  # honest -- no churn to divide by


async def test_retention_rate_is_the_complement_of_churn(client, db_session, register_payload):
    from api.models.admin import Plan, Subscription, SubscriptionStatus

    admin_token, _admin = await _make_superadmin(client, db_session, register_payload)
    org = (await client.post("/organizations", json={"name": "Retention Co"}, headers=_auth_header(admin_token))).json()
    plan = Plan(key="retention-test-plan", name="Test", monthly_price_cents=1000)
    db_session.add(plan)
    await db_session.flush()
    await client.get(f"/organizations/{org['id']}/billing/subscription", headers=_auth_header(admin_token))
    sub = await db_session.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(org["id"])))
    sub.plan_id = plan.id
    sub.status = SubscriptionStatus.canceled
    sub.canceled_at = dt.datetime.now(dt.timezone.utc)
    await db_session.commit()

    churn = (await client.get("/analytics/business/churn", headers=_auth_header(admin_token))).json()
    retention = (await client.get("/analytics/business/retention", headers=_auth_header(admin_token))).json()
    assert abs(retention["retention_rate"] - (1 - churn["churn_rate"])) < 1e-9


async def test_revenue_trend_returns_a_real_daily_series(client, db_session, register_payload):
    admin_token, _admin = await _make_superadmin(client, db_session, register_payload)
    response = await client.get("/analytics/business/revenue/trend?date_range=7d", headers=_auth_header(admin_token))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 8  # inclusive of both endpoints
    assert all("date" in point and "mrr_cents" in point for point in body)


async def test_customers_endpoint_counts_real_subscriptions(client, db_session, register_payload):
    admin_token, _admin = await _make_superadmin(client, db_session, register_payload)
    org = (await client.post("/organizations", json={"name": "New Customer Co"}, headers=_auth_header(admin_token))).json()
    await client.get(f"/organizations/{org['id']}/billing/subscription", headers=_auth_header(admin_token))  # lazily creates the real Subscription row

    response = await client.get("/analytics/business/customers", headers=_auth_header(admin_token))
    assert response.status_code == 200
    assert response.json()["total_customers"] >= 1
