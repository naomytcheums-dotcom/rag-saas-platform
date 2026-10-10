"""Cancellation lot: every cancellation path reaches the provider, never claims more than the provider did, keeps a pending
synchronization visible, and respects permissions and tenant isolation.

Stripe and Paystack are mocked here (no payment key, no network): this proves the platform's behaviour around the provider calls, NOT
the providers' real behaviour. Real sandbox runs are blocked until test keys are available.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select

from api.models.admin import Subscription, SubscriptionStatus
from api.models.user import UserRole
from api.routers import billing as billing_router
from api.services import billing_paystack, billing_stripe
from test_document_idor import make_tenants
from test_p1_backoffice_and_suspension import _bearer, _platform_user
from test_p1_bill003_005_006_stripe_chain import _provider_managed


async def _sub(db_session, org_id):
    db_session.expire_all()
    return await db_session.scalar(select(Subscription).where(Subscription.organization_id == org_id).execution_options(populate_existing=True))


async def _paystack_managed(client, db_session, monkeypatch, label):
    (headers, org_id, _user), (headers_b, _org_b, _ub) = await make_tenants(client, db_session, monkeypatch, label)
    from api.services import admin_subscriptions

    sub = await admin_subscriptions.get_or_create_subscription(db_session, org_id)
    sub.paystack_subscription_code = "SUB_1"
    sub.status = SubscriptionStatus.active
    sub_id = sub.id
    superadmin = await _platform_user(db_session, f"super-{label}@example.com", UserRole.superadmin)
    super_headers = _bearer(superadmin.id)
    await db_session.commit()
    return headers, headers_b, org_id, sub_id, super_headers


# ------------------------------------------------------------ Paystack


async def test_a_back_office_cancellation_of_a_paystack_subscription_stays_scheduled_until_paystack_confirms(client, db_session, monkeypatch):
    _h, _hb, org_id, sub_id, super_headers = await _paystack_managed(client, db_session, monkeypatch, "pscancel")
    disable = AsyncMock()
    with patch.object(billing_paystack, "cancel_paystack_subscription", disable):
        response = await client.post(f"/admin/subscriptions/{sub_id}/cancel", json={"reason": "fraud"}, headers=super_headers)
    assert response.status_code == 200, response.text
    disable.assert_awaited_once()
    sub = await _sub(db_session, org_id)
    assert sub.status == SubscriptionStatus.active and sub.canceled_at is not None and sub.cancel_reason == "fraud", \
        "Paystack only disables at the end of the period: the status must not claim more than the provider did"
    await billing_paystack.handle_paystack_webhook(db_session, {"event": "subscription.disable", "data": {"id": 9001, "subscription_code": "SUB_1", "customer": {}, "metadata": {"organization_id": str(org_id)}}})
    assert (await _sub(db_session, org_id)).status == SubscriptionStatus.canceled


async def test_a_paystack_failure_or_timeout_changes_nothing(client, db_session, monkeypatch):
    _h, _hb, org_id, sub_id, super_headers = await _paystack_managed(client, db_session, monkeypatch, "psfail")
    for error in (RuntimeError("secret detail"), TimeoutError("took too long")):
        with patch.object(billing_paystack, "cancel_paystack_subscription", AsyncMock(side_effect=error)):
            response = await client.post(f"/admin/subscriptions/{sub_id}/cancel", json={"reason": "x"}, headers=super_headers)
        assert response.status_code == 502 and "secret detail" not in response.text
    sub = await _sub(db_session, org_id)
    assert sub.status == SubscriptionStatus.active and sub.canceled_at is None


async def test_the_organization_cancellation_of_a_paystack_subscription_is_scheduled_too(client, db_session, monkeypatch):
    headers, _hb, org_id, _sub_id, _s = await _paystack_managed(client, db_session, monkeypatch, "psorg")
    with patch.object(billing_paystack, "cancel_paystack_subscription", AsyncMock()):
        response = await client.post(f"/organizations/{org_id}/billing/cancel", json={"reason": "too dear"}, headers=headers)
    assert response.status_code == 200 and response.json()["status"] == "active" and response.json()["canceled_at"] is not None


# ------------------------------------------------------------ provider-level routes keep the local state coherent


async def test_the_stripe_cancel_route_records_a_pending_cancellation(client, db_session, monkeypatch):
    headers, org_id, _plans = await _provider_managed(client, db_session, monkeypatch, "stripecancelroute")
    fake = MagicMock()
    with patch.object(billing_stripe, "_client", return_value=fake):
        response = await client.post(f"/organizations/{org_id}/billing/stripe/cancel", headers=headers)
    assert response.status_code == 204
    fake.Subscription.modify.assert_called_once_with("sub_TEST1", cancel_at_period_end=True)
    sub = await _sub(db_session, org_id)
    assert sub.status == SubscriptionStatus.active and sub.canceled_at is not None, "pending cancellation visible, not final"


async def test_an_immediate_stripe_cancellation_waits_for_the_provider_event_to_end_the_subscription(client, db_session, monkeypatch):
    headers, org_id, _plans = await _provider_managed(client, db_session, monkeypatch, "stripeimmediate")
    fake = MagicMock()
    with patch.object(billing_stripe, "_client", return_value=fake):
        response = await client.post(f"/organizations/{org_id}/billing/stripe/cancel?at_period_end=false", headers=headers)
    assert response.status_code == 204
    fake.Subscription.cancel.assert_called_once_with("sub_TEST1")
    sub = await _sub(db_session, org_id)
    assert sub.status == SubscriptionStatus.active and sub.canceled_at is not None


async def test_the_unified_cancel_route_records_a_pending_cancellation(client, db_session, monkeypatch):
    headers, org_id, _plans = await _provider_managed(client, db_session, monkeypatch, "unifiedcancel")
    provider = MagicMock()
    provider.name = "stripe"
    provider.cancel_subscription = AsyncMock()
    with patch.object(billing_router, "resolve_provider_for_organization", AsyncMock(return_value=provider)):
        response = await client.post(f"/organizations/{org_id}/billing/cancel-active-subscription", headers=headers)
    assert response.status_code == 204
    provider.cancel_subscription.assert_awaited_once()
    assert (await _sub(db_session, org_id)).canceled_at is not None


async def test_a_provider_level_cancellation_that_fails_records_nothing(client, db_session, monkeypatch):
    headers, org_id, _plans = await _provider_managed(client, db_session, monkeypatch, "unifiedfail")
    provider = MagicMock()
    provider.name = "stripe"
    provider.cancel_subscription = AsyncMock(side_effect=billing_router.ProviderNotConfiguredError("not configured"))
    with patch.object(billing_router, "resolve_provider_for_organization", AsyncMock(return_value=provider)):
        response = await client.post(f"/organizations/{org_id}/billing/cancel-active-subscription", headers=headers)
    assert response.status_code == 501
    assert (await _sub(db_session, org_id)).canceled_at is None


# ------------------------------------------------------------ permissions and isolation on every path


async def test_nobody_else_can_cancel_through_any_path(client, db_session, monkeypatch):
    (headers_a, org_a, _ua), (headers_b, _org_b, _ub) = await make_tenants(client, db_session, monkeypatch, "cancelscope")
    fake = MagicMock()
    paths = (("POST", f"/organizations/{org_a}/billing/cancel", {"reason": "x"}), ("POST", f"/organizations/{org_a}/billing/stripe/cancel", None),
             ("POST", f"/organizations/{org_a}/billing/cancel-active-subscription", None), ("POST", f"/organizations/{org_a}/billing/reactivate", None))
    with patch.object(billing_stripe, "_client", return_value=fake), patch.object(billing_paystack, "cancel_paystack_subscription", AsyncMock()) as disable:
        for method, url, body in paths:
            assert (await client.request(method, url, json=body, headers=headers_b)).status_code == 404, url  # another organization's owner
            assert (await client.request(method, url, json=body)).status_code in (401, 403), url  # anonymous
    fake.Subscription.modify.assert_not_called()
    fake.Subscription.cancel.assert_not_called()
    disable.assert_not_awaited()
    assert headers_a  # the legitimate owner is covered by the other tests of this module
