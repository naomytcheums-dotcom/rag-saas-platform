"""Partie 11.4 -- plans/subscriptions, real CRUD + real (honestly-zero) revenue math."""


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _make_admin_and_org(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    org_id = (await client.post("/organizations", json={"name": "Sub Org"}, headers=_auth_header(token))).json()["id"]
    user.role = UserRole.admin
    await db_session.commit()
    return token, user, org_id


async def test_free_plan_auto_created_for_new_organization(client, db_session, register_payload):
    token, _, org_id = await _make_admin_and_org(client, db_session, register_payload)
    billing = await client.get(f"/admin/organizations/{org_id}/billing", headers=_auth_header(token))
    assert billing.status_code == 200

    plans = await client.get("/admin/plans", headers=_auth_header(token))
    assert any(p["key"] == "free" and p["monthly_price_cents"] == 0 for p in plans.json())


async def test_revenue_stats_are_honestly_zero_without_a_real_paid_plan(client, db_session, register_payload):
    token, _, org_id = await _make_admin_and_org(client, db_session, register_payload)
    await client.get(f"/admin/organizations/{org_id}/billing", headers=_auth_header(token))  # ensures a real subscription row exists

    stats = await client.get("/admin/subscriptions/stats", headers=_auth_header(token))
    assert stats.status_code == 200
    assert stats.json()["mrr_cents"] == 0
    assert stats.json()["arr_cents"] == 0


async def test_create_paid_plan_and_assign_changes_real_mrr(client, db_session, register_payload):
    token, _, org_id = await _make_admin_and_org(client, db_session, register_payload)
    billing = await client.get(f"/admin/organizations/{org_id}/billing", headers=_auth_header(token))
    sub_id = billing.json()["subscription_id"]

    create_plan = await client.post("/admin/plans", json={"key": "pro", "name": "Pro", "monthly_price_cents": 2900}, headers=_auth_header(token))
    assert create_plan.status_code == 201
    plan_id = create_plan.json()["id"]

    update_response = await client.patch(f"/admin/subscriptions/{sub_id}", json={"plan_id": plan_id}, headers=_auth_header(token))
    assert update_response.status_code == 200

    stats = await client.get("/admin/subscriptions/stats", headers=_auth_header(token))
    assert stats.json()["mrr_cents"] == 2900
    assert stats.json()["arr_cents"] == 2900 * 12


async def test_cancel_subscription(client, db_session, register_payload):
    token, _, org_id = await _make_admin_and_org(client, db_session, register_payload)
    billing = await client.get(f"/admin/organizations/{org_id}/billing", headers=_auth_header(token))
    sub_id = billing.json()["subscription_id"]

    response = await client.post(f"/admin/subscriptions/{sub_id}/cancel", json={"reason": "no longer needed"}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["status"] == "canceled"


async def test_extend_subscription(client, db_session, register_payload):
    token, _, org_id = await _make_admin_and_org(client, db_session, register_payload)
    billing = await client.get(f"/admin/organizations/{org_id}/billing", headers=_auth_header(token))
    sub_id = billing.json()["subscription_id"]

    response = await client.post(f"/admin/subscriptions/{sub_id}/extend", json={"days": 30}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["current_period_end"] is not None


async def test_refund_refuses_honestly_without_a_real_payment_processor(client, db_session, register_payload):
    token, _, org_id = await _make_admin_and_org(client, db_session, register_payload)
    billing = await client.get(f"/admin/organizations/{org_id}/billing", headers=_auth_header(token))
    sub_id = billing.json()["subscription_id"]

    response = await client.post(f"/admin/subscriptions/{sub_id}/refund", headers=_auth_header(token))
    assert response.status_code == 501
