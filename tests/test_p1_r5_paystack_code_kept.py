"""R5: a Paystack `subscription.create` that carries no subscription_code must not erase the code already stored (it is the only handle
used later to cancel or recognize that subscription at Paystack)."""

from sqlalchemy import select

from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.billing import PaymentCustomer, PaymentProvider
from api.services import admin_subscriptions, billing_paystack
from test_document_idor import make_tenants


async def _org(client, db_session, monkeypatch, label):
    (_h, org_id, _u), _other = await make_tenants(client, db_session, monkeypatch, label)
    await admin_subscriptions.ensure_default_plans_seeded(db_session)
    pro = await db_session.scalar(select(Plan).where(Plan.key == "pro"))
    pro.paystack_plan_code_monthly = "PLN_pro_m"
    db_session.add(PaymentCustomer(organization_id=org_id, provider=PaymentProvider.paystack, external_customer_id="CUS_r5"))
    sub = await admin_subscriptions.get_or_create_subscription(db_session, org_id)
    sub.paystack_subscription_code = "SUB_KEEP"
    sub.status = SubscriptionStatus.active
    await db_session.commit()
    return org_id


async def _code(db_session, org_id):
    db_session.expire_all()
    return (await db_session.scalar(select(Subscription).where(Subscription.organization_id == org_id))).paystack_subscription_code


def _event(object_id, **data):
    return {"event": "subscription.create", "data": {"id": object_id, "customer": {"customer_code": "CUS_r5"}, **data}}


async def test_a_create_event_without_a_code_keeps_the_stored_code(client, db_session, monkeypatch):
    org_id = await _org(client, db_session, monkeypatch, "r5nocode")
    await billing_paystack.handle_paystack_webhook(db_session, _event(7001, plan={"plan_code": "PLN_pro_m"}))
    assert await _code(db_session, org_id) == "SUB_KEEP"


async def test_a_blank_code_does_not_erase_it_either(client, db_session, monkeypatch):
    org_id = await _org(client, db_session, monkeypatch, "r5blank")
    await billing_paystack.handle_paystack_webhook(db_session, _event(7002, subscription_code=""))
    assert await _code(db_session, org_id) == "SUB_KEEP"


async def test_a_create_event_with_a_new_code_still_replaces_it(client, db_session, monkeypatch):
    org_id = await _org(client, db_session, monkeypatch, "r5new")
    await billing_paystack.handle_paystack_webhook(db_session, _event(7003, subscription_code="SUB_NEW", plan={"plan_code": "PLN_pro_m"}))
    assert await _code(db_session, org_id) == "SUB_NEW"
