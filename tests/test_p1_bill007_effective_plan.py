"""BILL-007: access must follow the subscription's real state -- a canceled subscription keeps its plan only until the paid period
ends, a past-due one only for the grace period, a pending one never; a lapsed organization is held to the free plan's limits."""

import datetime as dt

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.admin import SubscriptionStatus
from test_p1_bill003_005_006_stripe_chain import NOW, _org_with_stripe_customer, _subscription


@pytest.mark.parametrize("status, period_end_days, grace, expected_paid", [
    (SubscriptionStatus.active, None, 7, True),
    (SubscriptionStatus.active, 10, 7, True),
    (SubscriptionStatus.active, -3, 7, True),
    (SubscriptionStatus.active, -8, 7, False),
    (SubscriptionStatus.past_due, -3, 7, True),
    (SubscriptionStatus.past_due, -8, 7, False),
    (SubscriptionStatus.past_due, None, 7, True),
    (SubscriptionStatus.canceled, 10, 7, True),
    (SubscriptionStatus.canceled, -1, 7, False),
    (SubscriptionStatus.canceled, None, 7, False),
    (SubscriptionStatus.pending, 10, 7, False),
    (SubscriptionStatus.pending, None, 7, False),
    (SubscriptionStatus.active, -3, 0, False),
])
async def test_effective_plan_follows_status_and_period(client, db_session, monkeypatch, status, period_end_days, grace, expected_paid):
    from api.services.billing_usage import get_effective_plan

    monkeypatch.setattr(settings, "BILLING_GRACE_PERIOD_DAYS", grace)
    _h, org_id, _u, plans = await _org_with_stripe_customer(client, db_session, monkeypatch, "entitle")
    sub = await _subscription(db_session, org_id)
    sub.plan_id, sub.status = plans["pro"].id, status
    sub.current_period_end = NOW + dt.timedelta(days=period_end_days) if period_end_days is not None else None
    await db_session.commit()

    plan = await get_effective_plan(db_session, org_id)

    assert plan.key == ("pro" if expected_paid else "free")


async def test_a_lapsed_paid_subscription_is_held_to_the_free_plan_limit(client, db_session, monkeypatch):
    from api.models.document import Document
    from api.services.billing_usage import check_plan_resource_limit

    _h, org_id, user_id, plans = await _org_with_stripe_customer(client, db_session, monkeypatch, "limits")
    plans["free"].max_documents = 1
    plans["pro"].max_documents = 100
    sub = await _subscription(db_session, org_id)
    sub.plan_id, sub.status, sub.current_period_end = plans["pro"].id, SubscriptionStatus.canceled, NOW - dt.timedelta(days=1)
    db_session.add_all([
        Document(organization_id=org_id, created_by=user_id, name=f"d{i}.txt", file_key=f"k{i}", file_size=1, file_type="text/plain", status="completed")
        for i in range(2)
    ])
    await db_session.commit()
    within, count, limit = await check_plan_resource_limit(db_session, org_id, "documents")
    assert (within, count, limit) == (False, 2, 1)
    sub.status, sub.current_period_end = SubscriptionStatus.active, NOW + dt.timedelta(days=20)
    await db_session.commit()
    within, count, limit = await check_plan_resource_limit(db_session, org_id, "documents")
    assert (within, count, limit) == (True, 2, 100)
