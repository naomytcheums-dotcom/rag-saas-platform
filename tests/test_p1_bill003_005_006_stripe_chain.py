"""P1 billing chain (BILL-003, 004, 005, 006, 007, 009, 010): a paid checkout must end in a paid plan, a successful payment must not
fail the webhook, cancelling must cancel at the provider, access must follow the subscription's real state, and invoices/credits
must match what was actually sold. Stripe is mocked; no payment is made and no network call leaves the process."""

import datetime as dt
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.billing import PaymentCustomer, PaymentProvider
from api.models.notification import Notification
from api.services import admin_subscriptions, billing_stripe
from test_document_idor import make_tenants

CUSTOMER = "cus_TEST123"
NOW = dt.datetime.now(dt.timezone.utc)


def _epoch(days: int) -> int:
    return int((NOW + dt.timedelta(days=days)).timestamp())


async def _org_with_stripe_customer(client, db_session, monkeypatch, label="bill"):
    (headers, org_id, user_id), _other = await make_tenants(client, db_session, monkeypatch, label)
    await admin_subscriptions.ensure_default_plans_seeded(db_session)
    plans = {plan.key: plan for plan in (await db_session.scalars(select(Plan))).all()}
    plans["pro"].stripe_price_id_monthly = "price_pro_m"
    plans["pro"].stripe_price_id_yearly = "price_pro_y"
    plans["starter"].stripe_price_id_monthly = "price_starter_m"
    db_session.add(PaymentCustomer(organization_id=org_id, provider=PaymentProvider.stripe, external_customer_id=CUSTOMER))
    await admin_subscriptions.get_or_create_subscription(db_session, org_id)
    await db_session.commit()
    return headers, org_id, user_id, plans


def _event(event_type, obj):
    return {"id": f"evt_{uuid.uuid4().hex}", "type": event_type, "data": {"object": obj}}


def _stripe_subscription(price_id="price_pro_m", status="active", **extra):
    return {
        "id": "sub_TEST1", "object": "subscription", "customer": CUSTOMER, "status": status, "metadata": {},
        "current_period_end": _epoch(30), "items": {"data": [{"price": {"id": price_id}}]}, **extra,
    }


async def _subscription(db_session, org_id):
    await db_session.commit()
    return await db_session.scalar(
        select(Subscription).where(Subscription.organization_id == org_id).execution_options(populate_existing=True)
    )


# ------------------------------------------------------------ BILL-003: a paid subscription reaches the plan


async def test_subscription_event_without_metadata_is_matched_through_the_stripe_customer(client, db_session, monkeypatch):
    _h, org_id, _u, plans = await _org_with_stripe_customer(client, db_session, monkeypatch)

    applied = await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.created", _stripe_subscription()))

    sub = await _subscription(db_session, org_id)
    assert applied is True
    assert sub.plan_id == plans["pro"].id and sub.billing_period == "monthly"
    assert sub.status == SubscriptionStatus.active
    assert sub.stripe_subscription_id == "sub_TEST1"
    assert sub.current_period_end is not None and abs(sub.current_period_end.replace(tzinfo=dt.timezone.utc) - (NOW + dt.timedelta(days=30))) < dt.timedelta(minutes=5)


async def test_yearly_price_selects_the_yearly_period(client, db_session, monkeypatch):
    _h, org_id, _u, plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.updated", _stripe_subscription("price_pro_y")))
    sub = await _subscription(db_session, org_id)
    assert sub.plan_id == plans["pro"].id and sub.billing_period == "yearly"


async def test_the_period_end_moves_with_the_new_api_layout(client, db_session, monkeypatch):
    """Recent Stripe API versions report current_period_end on the subscription item, not on the subscription."""
    _h, org_id, _u, _plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    subscription = _stripe_subscription()
    del subscription["current_period_end"]
    subscription["items"]["data"][0]["current_period_end"] = _epoch(45)
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.updated", subscription))
    sub = await _subscription(db_session, org_id)
    assert abs(sub.current_period_end.replace(tzinfo=dt.timezone.utc) - (NOW + dt.timedelta(days=45))) < dt.timedelta(minutes=5)


async def test_a_price_unknown_to_the_catalog_never_changes_the_plan(client, db_session, monkeypatch):
    _h, org_id, _u, plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    before = (await _subscription(db_session, org_id))
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.updated", _stripe_subscription("price_unknown")))
    sub = await _subscription(db_session, org_id)
    assert sub.plan_id == before.plan_id and sub.plan_id != plans["pro"].id
    assert sub.stripe_subscription_id == "sub_TEST1"


@pytest.mark.parametrize("stripe_status, expected", [
    ("active", SubscriptionStatus.active), ("trialing", SubscriptionStatus.active), ("past_due", SubscriptionStatus.past_due),
    ("unpaid", SubscriptionStatus.past_due), ("paused", SubscriptionStatus.past_due), ("incomplete", SubscriptionStatus.pending),
    ("incomplete_expired", SubscriptionStatus.canceled), ("canceled", SubscriptionStatus.canceled),
])
async def test_every_stripe_status_maps_explicitly(client, db_session, monkeypatch, stripe_status, expected):
    _h, org_id, _u, _plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.updated", _stripe_subscription(status=stripe_status)))
    assert (await _subscription(db_session, org_id)).status == expected


async def test_an_unknown_status_changes_nothing(client, db_session, monkeypatch):
    _h, org_id, _u, _plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    before = await _subscription(db_session, org_id)
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.updated", _stripe_subscription(status="something_new")))
    after = await _subscription(db_session, org_id)
    assert (after.status, after.plan_id, after.stripe_subscription_id) == (before.status, before.plan_id, before.stripe_subscription_id)


async def test_a_pending_subscription_does_not_grant_the_plan(client, db_session, monkeypatch):
    _h, org_id, _u, plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.created", _stripe_subscription(status="incomplete")))
    sub = await _subscription(db_session, org_id)
    assert sub.status == SubscriptionStatus.pending and sub.plan_id != plans["pro"].id


async def test_metadata_naming_another_organization_than_the_customer_is_ignored(client, db_session, monkeypatch):
    _h, org_id, _u, plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    other_org = uuid.uuid4()
    subscription = _stripe_subscription(metadata={"organization_id": str(other_org)})
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.created", subscription))
    sub = await _subscription(db_session, org_id)
    assert sub.plan_id != plans["pro"].id and sub.stripe_subscription_id is None
    assert await db_session.scalar(select(Subscription).where(Subscription.organization_id == other_org)) is None


async def test_metadata_alone_still_works_without_a_customer_mapping(client, db_session, monkeypatch):
    _h, org_id, _u, plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    subscription = _stripe_subscription(metadata={"organization_id": str(org_id)})
    subscription["customer"] = "cus_NOT_MAPPED"
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.created", subscription))
    assert (await _subscription(db_session, org_id)).plan_id == plans["pro"].id


async def test_a_paid_subscription_checkout_links_the_stripe_subscription(client, db_session, monkeypatch):
    _h, org_id, _u, plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    session = {
        "id": "cs_test_1", "object": "checkout.session", "mode": "subscription", "payment_status": "paid", "customer": CUSTOMER,
        "client_reference_id": str(org_id), "subscription": "sub_FROM_CHECKOUT",
        "metadata": {"organization_id": str(org_id), "plan_id": str(plans["pro"].id), "billing_period": "yearly"},
    }
    await billing_stripe.handle_stripe_webhook(db_session, _event("checkout.session.completed", session))
    sub = await _subscription(db_session, org_id)
    assert sub.stripe_subscription_id == "sub_FROM_CHECKOUT" and sub.plan_id == plans["pro"].id and sub.billing_period == "yearly"


async def test_an_unpaid_subscription_checkout_grants_nothing(client, db_session, monkeypatch):
    _h, org_id, _u, plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    session = {
        "id": "cs_test_2", "mode": "subscription", "payment_status": "unpaid", "customer": CUSTOMER, "subscription": "sub_X",
        "metadata": {"plan_id": str(plans["pro"].id)},
    }
    await billing_stripe.handle_stripe_webhook(db_session, _event("checkout.session.completed", session))
    sub = await _subscription(db_session, org_id)
    assert sub.plan_id != plans["pro"].id and sub.stripe_subscription_id is None


async def test_the_checkout_session_carries_the_organization_on_the_subscription_too(db_session):
    org_id, plan_id = uuid.uuid4(), uuid.uuid4()
    fake = MagicMock()
    fake.Customer.create.return_value = {"id": CUSTOMER}
    fake.checkout.Session.create.return_value = {"url": "https://checkout.stripe.test/s/1"}
    with patch.object(billing_stripe, "_client", return_value=fake):
        url = await billing_stripe.create_checkout_session(
            db_session, org_id, price_id="price_pro_m", email="a@example.com", org_name="Acme", plan_id=plan_id, billing_period="monthly",
        )
    kwargs = fake.checkout.Session.create.call_args.kwargs
    assert url == "https://checkout.stripe.test/s/1"
    assert kwargs["client_reference_id"] == str(org_id)
    assert kwargs["subscription_data"]["metadata"] == {"organization_id": str(org_id), "plan_id": str(plan_id), "billing_period": "monthly"}
    assert kwargs["metadata"]["organization_id"] == str(org_id)


async def test_subscription_deletion_cancels_and_cancel_at_period_end_is_recorded(client, db_session, monkeypatch):
    _h, org_id, _u, _plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.updated", _stripe_subscription(cancel_at_period_end=True)))
    scheduled = await _subscription(db_session, org_id)
    assert scheduled.status == SubscriptionStatus.active and scheduled.canceled_at is not None
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.updated", _stripe_subscription(cancel_at_period_end=False)))
    assert (await _subscription(db_session, org_id)).canceled_at is None
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.deleted", _stripe_subscription(status="canceled")))
    ended = await _subscription(db_session, org_id)
    assert ended.status == SubscriptionStatus.canceled and ended.canceled_at is not None


# ------------------------------------------------------------ BILL-005: a successful payment is a 200 with a notification


async def test_invoice_paid_reactivates_notifies_and_extends_the_period_without_failing(client, db_session, monkeypatch):
    _h, org_id, _u, _plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    sub = await _subscription(db_session, org_id)
    sub.status = SubscriptionStatus.past_due
    sub.current_period_end = NOW - dt.timedelta(days=2)
    await db_session.commit()
    invoice = {
        "id": "in_1", "object": "invoice", "customer": CUSTOMER, "subscription": "sub_TEST1",
        "lines": {"data": [{"period": {"start": _epoch(0), "end": _epoch(30)}}]},
    }

    applied = await billing_stripe.handle_stripe_webhook(db_session, _event("invoice.paid", invoice))

    sub = await _subscription(db_session, org_id)
    assert applied is True and sub.status == SubscriptionStatus.active
    assert sub.current_period_end.replace(tzinfo=dt.timezone.utc) > NOW + dt.timedelta(days=29)
    notifications = (await db_session.scalars(select(Notification).where(Notification.organization_id == org_id, Notification.type == "billing_payment_succeeded"))).all()
    assert len(notifications) == 1 and "Payment received" in notifications[0].title


async def test_the_webhook_route_answers_200_for_a_successful_payment(client, db_session, monkeypatch):
    _h, org_id, _u, _plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    sub = await _subscription(db_session, org_id)
    sub.status = SubscriptionStatus.past_due
    await db_session.commit()
    event = _event("invoice.paid", {"id": "in_2", "customer": CUSTOMER, "lines": {"data": []}})
    monkeypatch.setattr(billing_stripe, "verify_webhook_signature", lambda payload, header: event)

    response = await client.post("/billing/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})

    assert response.status_code == 200 and response.json() == {"received": True, "applied": True}
    assert (await _subscription(db_session, org_id)).status == SubscriptionStatus.active


async def test_a_failing_notification_never_fails_the_webhook_or_loses_the_state_change(client, db_session, monkeypatch):
    _h, org_id, _u, _plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    sub = await _subscription(db_session, org_id)
    sub.status = SubscriptionStatus.past_due
    await db_session.commit()
    boom = AsyncMock(side_effect=TypeError("notification layer is broken"))
    with patch("api.services.notifications.notify_billing_payment_succeeded", boom):
        applied = await billing_stripe.handle_stripe_webhook(db_session, _event("invoice.paid", {"id": "in_3", "customer": CUSTOMER}))
    assert applied is True and boom.await_count == 1
    assert (await _subscription(db_session, org_id)).status == SubscriptionStatus.active


async def test_payment_failure_marks_past_due_and_notifies_by_customer(client, db_session, monkeypatch):
    _h, org_id, _u, _plans = await _org_with_stripe_customer(client, db_session, monkeypatch)
    await billing_stripe.handle_stripe_webhook(db_session, _event("invoice.payment_failed", {"id": "in_4", "customer": CUSTOMER}))
    assert (await _subscription(db_session, org_id)).status == SubscriptionStatus.past_due
    failed = (await db_session.scalars(select(Notification).where(Notification.organization_id == org_id, Notification.type == "billing_payment_failed"))).all()
    assert len(failed) == 1


# ------------------------------------------------------------ BILL-006: cancelling cancels at the provider


def _fake_stripe():
    fake = MagicMock()
    return fake


async def _provider_managed(client, db_session, monkeypatch, label):
    headers, org_id, user_id, plans = await _org_with_stripe_customer(client, db_session, monkeypatch, label)
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.created", _stripe_subscription()))
    await db_session.commit()
    return headers, org_id, plans


async def test_cancelling_a_provider_subscription_cancels_at_the_provider_and_keeps_access_to_the_period_end(client, db_session, monkeypatch):
    headers, org_id, plans = await _provider_managed(client, db_session, monkeypatch, "cancel")
    fake = _fake_stripe()
    with patch.object(billing_stripe, "_client", return_value=fake):
        response = await client.post(f"/organizations/{org_id}/billing/cancel", json={"reason": "too dear"}, headers=headers)
    assert response.status_code == 200, response.text
    fake.Subscription.modify.assert_called_once_with("sub_TEST1", cancel_at_period_end=True)
    body = response.json()
    assert body["status"] == "active" and body["canceled_at"] is not None
    sub = await _subscription(db_session, org_id)
    assert sub.plan_id == plans["pro"].id and sub.cancel_reason == "too dear"


async def test_a_provider_failure_leaves_the_subscription_untouched(client, db_session, monkeypatch):
    headers, org_id, _plans = await _provider_managed(client, db_session, monkeypatch, "cancelfail")
    fake = _fake_stripe()
    fake.Subscription.modify.side_effect = RuntimeError("stripe is down: secret detail")
    with patch.object(billing_stripe, "_client", return_value=fake):
        response = await client.post(f"/organizations/{org_id}/billing/cancel", json={"reason": None}, headers=headers)
    assert response.status_code == 502 and "secret detail" not in response.text
    sub = await _subscription(db_session, org_id)
    assert sub.status == SubscriptionStatus.active and sub.canceled_at is None


async def test_a_subscription_without_a_provider_is_still_cancelled_locally(client, db_session, monkeypatch):
    (headers, org_id, _user), _other = await make_tenants(client, db_session, monkeypatch, "localcancel")
    fake = _fake_stripe()
    with patch.object(billing_stripe, "_client", return_value=fake):
        response = await client.post(f"/organizations/{org_id}/billing/cancel", json={"reason": None}, headers=headers)
    assert response.status_code == 200 and response.json()["status"] == "canceled"
    fake.Subscription.modify.assert_not_called()


async def test_reactivating_a_scheduled_cancellation_withdraws_it_at_the_provider(client, db_session, monkeypatch):
    headers, org_id, _plans = await _provider_managed(client, db_session, monkeypatch, "resume")
    fake = _fake_stripe()
    with patch.object(billing_stripe, "_client", return_value=fake):
        await client.post(f"/organizations/{org_id}/billing/cancel", json={"reason": None}, headers=headers)
        response = await client.post(f"/organizations/{org_id}/billing/reactivate", headers=headers)
    assert response.status_code == 200 and response.json()["canceled_at"] is None
    assert [call.kwargs for call in fake.Subscription.modify.call_args_list] == [{"cancel_at_period_end": True}, {"cancel_at_period_end": False}]


async def test_an_ended_provider_subscription_cannot_be_reactivated_locally(client, db_session, monkeypatch):
    headers, org_id, _plans = await _provider_managed(client, db_session, monkeypatch, "ended")
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.deleted", _stripe_subscription(status="canceled")))
    await db_session.commit()
    response = await client.post(f"/organizations/{org_id}/billing/reactivate", headers=headers)
    assert response.status_code == 409
    assert (await _subscription(db_session, org_id)).status == SubscriptionStatus.canceled
