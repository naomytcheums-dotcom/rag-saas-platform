"""BILL-017: an organization cannot move itself to a plan the platform has retired (`Plan.is_active = false`). The rest of the finding
(unknown plan -> 404, billing_period restricted to monthly/yearly) is already covered by tests/test_p0_billing_no_free_paid_plan.py."""

import uuid

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.admin import Plan, Subscription
from test_p0_billing_no_free_paid_plan import _auth, _current_plan_id, _org


async def _retired_plan(db_session, key: str, monthly: int = 0) -> uuid.UUID:
    plan = Plan(key=key, name=key, monthly_price_cents=monthly, yearly_price_cents=0, is_active=False)
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan.id


@pytest.mark.parametrize("route", ["subscribe", "upgrade", "downgrade"])
async def test_an_inactive_plan_cannot_be_selected_and_nothing_changes(client, db_session, register_payload, route):
    token, org_id = await _org(client, register_payload)
    retired = await _retired_plan(db_session, f"retired-{route}")
    await client.get(f"/organizations/{org_id}/billing/subscription", headers=_auth(token))
    before = await _current_plan_id(db_session, org_id)

    response = await client.post(f"/organizations/{org_id}/billing/{route}", json={"plan_id": str(retired)}, headers=_auth(token))

    assert response.status_code == 404 and response.json()["detail"] == "Plan not found"
    assert await _current_plan_id(db_session, org_id) == before


async def test_an_inactive_plan_is_refused_under_the_self_service_setting_too(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_ALLOW_SELF_SERVICE_PAID_PLANS", True)
    token, org_id = await _org(client, register_payload)
    retired = await _retired_plan(db_session, "retired-self-service", monthly=5000)
    await client.get(f"/organizations/{org_id}/billing/subscription", headers=_auth(token))
    before = await _current_plan_id(db_session, org_id)

    response = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": str(retired)}, headers=_auth(token))

    assert response.status_code == 404
    assert await _current_plan_id(db_session, org_id) == before


async def test_an_organization_already_on_a_retired_plan_can_keep_it(client, db_session, register_payload):
    token, org_id = await _org(client, register_payload)
    retired = await _retired_plan(db_session, "retired-current")
    await client.get(f"/organizations/{org_id}/billing/subscription", headers=_auth(token))
    sub = await db_session.scalar(select(Subscription).where(Subscription.organization_id == org_id))
    sub.plan_id = retired
    await db_session.commit()

    response = await client.post(f"/organizations/{org_id}/billing/subscribe", json={"plan_id": str(retired), "billing_period": "yearly"}, headers=_auth(token))

    assert response.status_code == 200, response.text
    assert await _current_plan_id(db_session, org_id) == retired
