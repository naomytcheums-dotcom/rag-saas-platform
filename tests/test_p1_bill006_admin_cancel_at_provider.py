"""V8: a back-office cancellation of a provider-managed subscription must cancel it at the provider too, otherwise the provider keeps
charging a customer whose subscription the platform shows as ended. Stripe is mocked; no call leaves the process."""

from unittest.mock import MagicMock, patch

from sqlalchemy import select

from api.models.admin import Subscription, SubscriptionStatus
from api.models.user import UserRole
from api.services import billing_stripe
from test_p1_backoffice_and_suspension import _bearer, _platform_user
from test_p1_bill003_005_006_stripe_chain import _event, _org_with_stripe_customer, _stripe_subscription


async def _managed(client, db_session, monkeypatch, label):
    _h, org_id, _u, _plans = await _org_with_stripe_customer(client, db_session, monkeypatch, label)
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.created", _stripe_subscription()))
    await db_session.commit()
    sub = await db_session.scalar(select(Subscription).where(Subscription.organization_id == org_id))
    superadmin = await _platform_user(db_session, f"super-{label}@example.com", UserRole.superadmin)
    return sub.id, _bearer(superadmin.id)


async def _status(db_session, sub_id):
    db_session.expire_all()
    return (await db_session.get(Subscription, sub_id)).status


async def test_an_admin_cancellation_cancels_at_stripe_immediately(client, db_session, monkeypatch):
    sub_id, headers = await _managed(client, db_session, monkeypatch, "admcancel")
    fake = MagicMock()
    with patch.object(billing_stripe, "_client", return_value=fake):
        response = await client.post(f"/admin/subscriptions/{sub_id}/cancel", json={"reason": "fraud"}, headers=headers)
    assert response.status_code == 200 and response.json()["status"] == "canceled"
    fake.Subscription.cancel.assert_called_once_with("sub_TEST1")
    fake.Subscription.modify.assert_not_called()


async def test_the_delete_route_cancels_at_stripe_too(client, db_session, monkeypatch):
    sub_id, headers = await _managed(client, db_session, monkeypatch, "admdelete")
    fake = MagicMock()
    with patch.object(billing_stripe, "_client", return_value=fake):
        response = await client.delete(f"/admin/subscriptions/{sub_id}", headers=headers)
    assert response.status_code == 200
    fake.Subscription.cancel.assert_called_once_with("sub_TEST1")


async def test_a_provider_failure_changes_nothing_and_leaks_nothing(client, db_session, monkeypatch):
    sub_id, headers = await _managed(client, db_session, monkeypatch, "admfail")
    fake = MagicMock()
    fake.Subscription.cancel.side_effect = RuntimeError("stripe down: secret detail")
    with patch.object(billing_stripe, "_client", return_value=fake):
        response = await client.post(f"/admin/subscriptions/{sub_id}/cancel", json={"reason": "x"}, headers=headers)
    assert response.status_code == 502 and "secret detail" not in response.text
    assert await _status(db_session, sub_id) == SubscriptionStatus.active


async def test_a_provider_that_is_no_longer_configured_refuses_instead_of_cancelling_only_locally(client, db_session, monkeypatch):
    sub_id, headers = await _managed(client, db_session, monkeypatch, "admnoconf")
    with patch.object(billing_stripe, "_client", side_effect=billing_stripe.StripeNotConfiguredError("not configured")):
        response = await client.post(f"/admin/subscriptions/{sub_id}/cancel", json={"reason": "x"}, headers=headers)
    assert response.status_code == 501
    assert await _status(db_session, sub_id) == SubscriptionStatus.active


async def test_an_already_canceled_subscription_does_not_call_the_provider_again(client, db_session, monkeypatch):
    sub_id, headers = await _managed(client, db_session, monkeypatch, "admtwice")
    fake = MagicMock()
    with patch.object(billing_stripe, "_client", return_value=fake):
        first = await client.post(f"/admin/subscriptions/{sub_id}/cancel", json={"reason": "x"}, headers=headers)
        second = await client.post(f"/admin/subscriptions/{sub_id}/cancel", json={"reason": "x"}, headers=headers)
    assert (first.status_code, second.status_code) == (200, 200)
    assert fake.Subscription.cancel.call_count == 1


async def test_a_subscription_without_a_provider_is_cancelled_locally_as_before(client, db_session, monkeypatch):
    _h, org_id, _u, _plans = await _org_with_stripe_customer(client, db_session, monkeypatch, "admlocal")
    sub = await db_session.scalar(select(Subscription).where(Subscription.organization_id == org_id))
    superadmin = await _platform_user(db_session, "super-admlocal@example.com", UserRole.superadmin)
    fake = MagicMock()
    with patch.object(billing_stripe, "_client", return_value=fake):
        response = await client.post(f"/admin/subscriptions/{sub.id}/cancel", json={"reason": "x"}, headers=_bearer(superadmin.id))
    assert response.status_code == 200 and response.json()["status"] == "canceled"
    fake.Subscription.cancel.assert_not_called()
