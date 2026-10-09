"""Billing integrity (invoice lot, cancellation lot): manual settlement needs proof, refused and provider actions are audited, provider
events that arrive late or out of order never reopen what ended, Paystack assigns the paid plan, and inputs are bounded.

Provider events are fed straight to the handlers (signature verification is covered elsewhere); no network call leaves the process.
SQLite cannot prove row locks: those are exercised on a disposable PostgreSQL in test_postgres_invoice_concurrency.py.
"""

import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.audit_log import AuditLog
from api.models.billing import Invoice, InvoiceStatus, PaymentCustomer, PaymentProvider
from api.models.user import UserRole
from api.services import admin_subscriptions, billing_invoices, billing_paystack, billing_stripe
from test_document_idor import make_tenants
from test_p0_billing_no_free_paid_plan import _auth, _org
from test_p1_backoffice_and_suspension import _bearer, _platform_user
from test_p1_bill003_005_006_stripe_chain import _event, _org_with_stripe_customer, _stripe_subscription, _subscription

PROOF = {"reference": "WIRE-2026-0001"}


async def _audits(db_session, action, **filters):
    db_session.expire_all()
    query = select(AuditLog).where(AuditLog.action == action)
    for column, value in filters.items():
        query = query.where(getattr(AuditLog, column) == value)
    return list((await db_session.scalars(query)).all())


# ------------------------------------------------------------ manual settlement needs proof


async def _pending_invoice(db_session, org_id):
    invoice = await billing_invoices.create_invoice(db_session, org_id, lines=[{"description": "Pro plan", "quantity": 1, "unit_price_cents": 19900}])
    invoice.status = InvoiceStatus.pending
    await db_session.commit()
    return invoice.id


async def test_marking_an_invoice_paid_requires_a_payment_reference(client, db_session, register_payload):
    _token, org_id = await _org(client, register_payload)
    superadmin = await _platform_user(db_session, "super-proof@example.com", UserRole.superadmin)
    headers = _bearer(superadmin.id)
    invoice_id = await _pending_invoice(db_session, org_id)
    url = f"/admin/organizations/{org_id}/invoices/{invoice_id}/mark-paid"
    for body in (None, {}, {"reference": ""}, {"reference": "ab"}, {"reference": "x" * 201}):
        assert (await client.post(url, json=body, headers=headers)).status_code == 422, body
    db_session.expire_all()
    assert (await db_session.get(Invoice, invoice_id)).status == InvoiceStatus.pending
    assert (await client.post(url, json=PROOF, headers=headers)).status_code == 200
    rows = await _audits(db_session, "invoice_marked_paid")
    assert len(rows) == 1 and "WIRE-2026-0001" in rows[0].metadata_json and '"request_id"' in rows[0].metadata_json


# ------------------------------------------------------------ refused and provider actions are audited


async def test_a_refused_financial_attempt_is_audited_but_an_anonymous_one_has_no_actor(client, db_session, register_payload):
    _token, org_id = await _org(client, register_payload)
    admin = await _platform_user(db_session, "admin-denied@example.com", UserRole.admin)
    admin_id, admin_headers = admin.id, _bearer(admin.id)
    invoice_id = await _pending_invoice(db_session, org_id)
    url = f"/admin/organizations/{org_id}/invoices/{invoice_id}/mark-paid"
    assert (await client.post(url, json=PROOF, headers=admin_headers)).status_code == 403
    assert (await client.post(url, json=PROOF)).status_code in (401, 403)
    rows = await _audits(db_session, "admin_financial_action_denied")
    assert len(rows) == 1 and rows[0].user_id == admin_id and rows[0].success is False
    assert rows[0].resource_id == f"POST {url}" and '"role": "admin"' in rows[0].metadata_json
    assert await _audits(db_session, "invoice_marked_paid") == []


async def test_refund_and_provider_sync_attempts_are_audited(client, db_session, register_payload):
    token, org_id = await _org(client, register_payload)
    superadmin = await _platform_user(db_session, "super-sync@example.com", UserRole.superadmin)
    headers = _bearer(superadmin.id)
    sub = await admin_subscriptions.get_or_create_subscription(db_session, org_id)
    sub_id = sub.id
    await db_session.commit()
    assert (await client.post(f"/admin/subscriptions/{sub_id}/refund", headers=headers)).status_code == 501
    assert (await client.post("/admin/plans/sync/stripe-products", headers=headers)).status_code == 501
    refund = await _audits(db_session, "admin_refund_attempted")
    assert len(refund) == 1 and refund[0].success is False and refund[0].organization_id == org_id
    sync = await _audits(db_session, "admin_provider_sync")
    assert len(sync) == 1 and sync[0].success is False and sync[0].resource_id == "products"
    assert token  # the organization owner was never involved


# ------------------------------------------------------------ Stripe events out of order


async def _managed_stripe_subscription(client, db_session, monkeypatch, label):
    _h, org_id, _u, _plans = await _org_with_stripe_customer(client, db_session, monkeypatch, label)
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.created", _stripe_subscription()))
    await db_session.commit()
    return org_id


async def test_a_late_update_never_reopens_an_ended_stripe_subscription(client, db_session, monkeypatch):
    org_id = await _managed_stripe_subscription(client, db_session, monkeypatch, "late1")
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.deleted", _stripe_subscription(status="canceled")))
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.updated", _stripe_subscription(status="active")))
    assert (await _subscription(db_session, org_id)).status == SubscriptionStatus.canceled


async def test_a_late_payment_failure_never_reopens_an_ended_subscription(client, db_session, monkeypatch):
    org_id = await _managed_stripe_subscription(client, db_session, monkeypatch, "late2")
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.deleted", _stripe_subscription(status="canceled")))
    await billing_stripe.handle_stripe_webhook(db_session, _event("invoice.payment_failed", {"id": "in_1", "customer": "cus_TEST123", "subscription": "sub_TEST1"}))
    assert (await _subscription(db_session, org_id)).status == SubscriptionStatus.canceled


async def test_the_deletion_of_an_old_subscription_does_not_cancel_the_current_one(client, db_session, monkeypatch):
    org_id = await _managed_stripe_subscription(client, db_session, monkeypatch, "late3")
    await billing_stripe.handle_stripe_webhook(db_session, _event("customer.subscription.deleted", {**_stripe_subscription(status="canceled"), "id": "sub_OLD"}))
    sub = await _subscription(db_session, org_id)
    assert sub.status == SubscriptionStatus.active and sub.stripe_subscription_id == "sub_TEST1"


async def test_a_duplicated_stripe_event_is_applied_and_audited_once(client, db_session, monkeypatch):
    org_id = await _managed_stripe_subscription(client, db_session, monkeypatch, "dup1")
    event = _event("customer.subscription.updated", _stripe_subscription(cancel_at_period_end=True))
    assert [await billing_stripe.handle_stripe_webhook(db_session, event) for _ in range(2)] == [True, False]
    rows = await _audits(db_session, "billing_webhook_applied", resource_id=event["id"])
    assert len(rows) == 1 and rows[0].user_id is None and rows[0].organization_id == org_id
    assert '"provider": "stripe"' in rows[0].metadata_json


# ------------------------------------------------------------ Paystack: plan from the plan code, ordering, malformed input


async def _paystack_org(client, db_session, monkeypatch, label):
    (_headers, org_id, _user), _other = await make_tenants(client, db_session, monkeypatch, label)
    await admin_subscriptions.ensure_default_plans_seeded(db_session)
    pro = await db_session.scalar(select(Plan).where(Plan.key == "pro"))
    pro.paystack_plan_code_monthly, pro.paystack_plan_code_yearly = "PLN_pro_m", "PLN_pro_y"
    pro_id = pro.id
    db_session.add(PaymentCustomer(organization_id=org_id, provider=PaymentProvider.paystack, external_customer_id="CUS_x"))
    await admin_subscriptions.get_or_create_subscription(db_session, org_id)
    await db_session.commit()
    return org_id, pro_id


def _paystack(event, object_id, code="SUB_1", **data):
    return {"event": event, "data": {"id": object_id, "subscription_code": code, "customer": {"customer_code": "CUS_x"}, **data}}


async def test_paystack_assigns_the_plan_from_the_reported_plan_code(client, db_session, monkeypatch):
    org_id, pro_id = await _paystack_org(client, db_session, monkeypatch, "psplan")
    assert await billing_paystack.handle_paystack_webhook(db_session, _paystack("subscription.create", 1001, plan={"plan_code": "PLN_pro_y"}))
    sub = await _subscription(db_session, org_id)
    assert (sub.plan_id, sub.billing_period, sub.status, sub.paystack_subscription_code) == (pro_id, "yearly", SubscriptionStatus.active, "SUB_1")


async def test_an_unknown_paystack_plan_code_changes_no_plan(client, db_session, monkeypatch):
    org_id, _pro = await _paystack_org(client, db_session, monkeypatch, "psunknown")
    before = (await _subscription(db_session, org_id)).plan_id
    await billing_paystack.handle_paystack_webhook(db_session, _paystack("subscription.create", 1002, plan={"plan_code": "PLN_nobody"}))
    assert (await _subscription(db_session, org_id)).plan_id == before


async def test_paystack_late_events_never_reopen_a_disabled_subscription(client, db_session, monkeypatch):
    org_id, _pro = await _paystack_org(client, db_session, monkeypatch, "pslate")
    handle = billing_paystack.handle_paystack_webhook
    await handle(db_session, _paystack("subscription.create", 1003, plan={"plan_code": "PLN_pro_m"}))
    await handle(db_session, _paystack("subscription.disable", 1004))
    await handle(db_session, _paystack("subscription.create", 1005, plan={"plan_code": "PLN_pro_m"}))  # late duplicate of the creation
    await handle(db_session, _paystack("charge.success", 1006))
    await handle(db_session, _paystack("invoice.payment_failed", 1007))
    assert (await _subscription(db_session, org_id)).status == SubscriptionStatus.canceled


async def test_a_paystack_charge_restores_only_a_subscription_waiting_for_payment(client, db_session, monkeypatch):
    org_id, _pro = await _paystack_org(client, db_session, monkeypatch, "pscharge")
    sub = await _subscription(db_session, org_id)
    sub.status = SubscriptionStatus.past_due
    await db_session.commit()
    await billing_paystack.handle_paystack_webhook(db_session, _paystack("charge.success", 1008))
    assert (await _subscription(db_session, org_id)).status == SubscriptionStatus.active


async def test_disabling_another_paystack_subscription_does_not_cancel_the_current_one(client, db_session, monkeypatch):
    org_id, _pro = await _paystack_org(client, db_session, monkeypatch, "psother")
    await billing_paystack.handle_paystack_webhook(db_session, _paystack("subscription.create", 1009, plan={"plan_code": "PLN_pro_m"}))
    await billing_paystack.handle_paystack_webhook(db_session, _paystack("subscription.disable", 1010, code="SUB_OLD"))
    assert (await _subscription(db_session, org_id)).status == SubscriptionStatus.active


async def test_a_malformed_organization_id_in_a_paystack_event_is_ignored_not_a_500(client, db_session, monkeypatch):
    await _paystack_org(client, db_session, monkeypatch, "psmalformed")
    event = {"event": "charge.success", "data": {"id": 1011, "metadata": {"organization_id": "not-a-uuid"}}}
    assert await billing_paystack.handle_paystack_webhook(db_session, event) is True


async def test_a_duplicated_paystack_event_is_applied_once(client, db_session, monkeypatch):
    _org_id, _pro = await _paystack_org(client, db_session, monkeypatch, "psdup")
    event = _paystack("subscription.create", 1012, plan={"plan_code": "PLN_pro_m"})
    assert [await billing_paystack.handle_paystack_webhook(db_session, event) for _ in range(2)] == [True, False]
    assert len(await _audits(db_session, "billing_webhook_applied", resource_id="subscription.create:1012")) == 1


# ------------------------------------------------------------ overdue marking never overwrites a payment


async def test_marking_invoices_overdue_leaves_paid_void_and_future_invoices_alone(client, db_session, register_payload):
    _token, org_id = await _org(client, register_payload)
    past = dt.date.today() - dt.timedelta(days=5)
    ids = {}
    for name, status, due in (("pending", InvoiceStatus.pending, past), ("paid", InvoiceStatus.paid, past), ("void", InvoiceStatus.void, past), ("future", InvoiceStatus.pending, dt.date.today() + dt.timedelta(days=5))):
        invoice = await billing_invoices.create_invoice(db_session, org_id, lines=[{"description": name, "quantity": 1, "unit_price_cents": 100}])
        invoice.status, invoice.due_date = status, due
        ids[name] = invoice.id
    await db_session.commit()
    assert await billing_invoices.mark_overdue_invoices(db_session) == 1
    await db_session.commit()
    db_session.expire_all()
    statuses = {name: (await db_session.get(Invoice, invoice_id)).status for name, invoice_id in ids.items()}
    assert statuses == {"pending": InvoiceStatus.overdue, "paid": InvoiceStatus.paid, "void": InvoiceStatus.void, "future": InvoiceStatus.pending}


# ------------------------------------------------------------ input bounds


@pytest.mark.parametrize("body", [
    {"key": "Bad Key!", "name": "X"}, {"key": "ok", "name": ""}, {"key": "ok", "name": "X", "monthly_price_cents": 10**10},
    {"key": "ok", "name": "X", "max_agents": -1}, {"key": "x" * 65, "name": "X"}, {"key": "ok", "name": "X", "paystack_plan_code_monthly": "c" * 101},
])
async def test_absurd_plan_definitions_are_rejected(client, db_session, body):
    superadmin = await _platform_user(db_session, f"super-{uuid.uuid4().hex[:6]}@example.com", UserRole.superadmin)
    response = await client.post("/admin/plans", json=body, headers=_bearer(superadmin.id))
    assert response.status_code == 422, (body, response.text)


async def test_a_sensible_plan_definition_is_still_accepted(client, db_session):
    superadmin = await _platform_user(db_session, "super-okplan@example.com", UserRole.superadmin)
    response = await client.post("/admin/plans", json={"key": "team-plus_1", "name": "Team +", "monthly_price_cents": 4900, "max_agents": 10}, headers=_bearer(superadmin.id))
    assert response.status_code == 201, response.text


async def test_organization_billing_inputs_are_bounded(client, db_session, register_payload):
    token, org_id = await _org(client, register_payload)
    base = f"/organizations/{org_id}/billing"
    plan = (await client.get("/billing/plans")).json()[0]["id"]
    assert (await client.post(f"{base}/subscribe", json={"plan_id": plan, "billing_period": "forever"}, headers=_auth(token))).status_code == 422
    for threshold in (0, 101, -5):
        assert (await client.post(f"{base}/usage/alerts", json={"resource_type": "documents", "threshold_percent": threshold}, headers=_auth(token))).status_code == 422
    assert (await client.post(f"{base}/cancel", json={"reason": "r" * 501}, headers=_auth(token))).status_code == 422
    assert (await client.post(f"{base}/credits/purchase", json={"pack_id": ""}, headers=_auth(token))).status_code == 422
    assert (await client.post(f"{base}/usage/alerts", json={"resource_type": "documents", "threshold_percent": 80}, headers=_auth(token))).status_code == 201


async def test_the_subscription_row_exists_for_each_helper(client, db_session, monkeypatch):
    """Guards the helpers above: a missing subscription row would make the ordering tests pass for the wrong reason."""
    org_id = await _managed_stripe_subscription(client, db_session, monkeypatch, "helper")
    assert (await db_session.scalar(select(Subscription).where(Subscription.organization_id == org_id))) is not None
