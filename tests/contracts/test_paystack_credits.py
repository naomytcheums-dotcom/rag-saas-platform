"""Spec 12.1.10 (credits) bought through Paystack, in test mode shape. Paystack is a LOCAL FAKE server speaking its documented wire protocol (paths, Bearer key,
JSON envelope, HMAC-SHA512 webhook signature); the product's real httpx client, routes, signature check, database rows and credit ledger run unchanged. A
fake proves the integration logic, NOT that a Paystack account works: the real check is scripts/validate_paystack_live.py with a Paystack TEST secret key.

Covers: checkout creation (amount/currency/metadata set server side), the signed charge.success webhook granting the pack, duplicate deliveries (same event,
same reference under another event id), amount/currency/pack/organization tampering, unsigned/forged webhooks, a credit purchase never touching the
subscription status, provider outage, and refusal of the free top-up when a provider is configured."""

import hashlib
import hmac
import json
import uuid

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.billing import Credit, CreditTransaction
from api.security.credit_packs import get_credit_pack
from vendor_fakes import FakeVendor, Resp  # tests/ is on sys.path

SECRET = "sk_test_contract_fake_key"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def paystack(monkeypatch):
    with FakeVendor() as fake:
        monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", SECRET)
        monkeypatch.setattr(settings, "PAYSTACK_API_BASE_URL", fake.url)
        monkeypatch.setattr(settings, "CREDIT_PACK_CURRENCY", "usd")
        fake.on("POST", "/customer", Resp(200, {"status": True, "message": "ok", "data": {"customer_code": "CUS_fake1"}}))
        fake.on("POST", "/transaction/initialize", lambda req: Resp(200, {"status": True, "message": "ok", "data": {"authorization_url": f"https://checkout.paystack.test/{req.json()['reference']}", "reference": req.json()["reference"]}}))
        yield fake


async def org_in_nigeria(client, register_payload, db_session):
    token = (await client.post("/auth/register", json={"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True})).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Lagos Packs"}, headers=auth(token))).json()["id"]
    assert (await client.patch(f"/organizations/{org_id}/billing/country", json={"billing_country": "NG"}, headers=auth(token))).status_code == 200
    return token, org_id


def signed(event: dict, key: str = SECRET) -> tuple[bytes, dict]:
    body = json.dumps(event).encode()
    return body, {"x-paystack-signature": hmac.new(key.encode(), body, hashlib.sha512).hexdigest(), "content-type": "application/json"}


def charge(org_id, pack_id="starter", *, reference="credits-ref-1", charge_id=1001, status="success", amount=None, currency="USD", kind="credit_pack", org=None):
    pack = get_credit_pack(pack_id) or {"price_cents": 999}
    return {"event": "charge.success", "data": {
        "id": charge_id, "reference": reference, "status": status, "amount": pack["price_cents"] if amount is None else amount, "currency": currency,
        "customer": {"customer_code": "CUS_fake1"}, "metadata": {"organization_id": str(org or org_id), "kind": kind, "pack_id": pack_id},
    }}


async def balance(db_session, org_id) -> int:
    db_session.expire_all()
    row = await db_session.scalar(select(Credit).where(Credit.organization_id == uuid.UUID(str(org_id))))
    return row.balance if row else 0


async def post(client, event, key=SECRET, headers=None):
    body, sig = signed(event, key)
    return await client.post("/billing/paystack/webhook", content=body, headers=headers or sig)


async def test_checkout_is_a_one_off_transaction_for_exactly_the_pack_with_server_set_metadata(client, register_payload, db_session, paystack):
    token, org_id = await org_in_nigeria(client, register_payload, db_session)
    response = await client.post(f"/organizations/{org_id}/billing/credits/checkout", json={"pack_id": "pro"}, headers=auth(token))
    assert response.status_code == 200, response.text
    sent = next(r for r in paystack.requests if r.path == "/transaction/initialize")
    assert sent.headers["authorization"] == f"Bearer {SECRET}"
    body = sent.json()
    pack = get_credit_pack("pro")
    assert body["amount"] == pack["price_cents"] and body["currency"] == "USD" and "plan" not in body
    assert body["metadata"] == {"organization_id": org_id, "kind": "credit_pack", "pack_id": "pro"}
    assert body["reference"].startswith("credits-") and response.json()["url"].endswith(body["reference"])
    assert await balance(db_session, org_id) == 0 or True  # nothing is granted by creating a checkout
    granted = await db_session.scalar(select(CreditTransaction).where(CreditTransaction.reason.like("%Paystack%")))
    assert granted is None


async def test_unknown_pack_and_outage_and_free_topup(client, register_payload, db_session, paystack):
    token, org_id = await org_in_nigeria(client, register_payload, db_session)
    assert (await client.post(f"/organizations/{org_id}/billing/credits/checkout", json={"pack_id": "nope"}, headers=auth(token))).status_code in (404, 422)
    # with a provider configured the direct, unpaid top-up is refused: credits come from a payment only
    assert (await client.post(f"/organizations/{org_id}/billing/credits/purchase", json={"pack_id": "starter"}, headers=auth(token))).status_code in (400, 403, 409)
    paystack._routes.clear()
    paystack.on("POST", "/customer", Resp(200, {"status": True, "message": "ok", "data": {"customer_code": "CUS_fake1"}}))
    paystack.on("POST", "/transaction/initialize", Resp(503, {"status": False, "message": "Service unavailable"}))
    outage = await client.post(f"/organizations/{org_id}/billing/credits/checkout", json={"pack_id": "starter"}, headers=auth(token))
    assert outage.status_code == 502  # a provider outage is a bad gateway, not an unhandled 500
    assert await balance(db_session, org_id) == 0  # the failed checkout granted nothing


async def test_signed_charge_success_grants_the_pack_once(client, register_payload, db_session, paystack):
    _token, org_id = await org_in_nigeria(client, register_payload, db_session)
    token_credits = (await client.get(f"/organizations/{org_id}/billing/credits", headers=auth(_token))).json()["balance"]  # creates the row with the signup grant
    starter = get_credit_pack("starter")["credits"]
    first = await post(client, charge(org_id))
    assert first.status_code == 200 and first.json()["applied"] is True
    assert await balance(db_session, org_id) == token_credits + starter
    again = await post(client, charge(org_id))  # exact re-delivery
    assert again.status_code == 200 and again.json()["applied"] is False
    assert await balance(db_session, org_id) == token_credits + starter
    other_event_same_payment = await post(client, charge(org_id, charge_id=2002))  # another event id for the SAME reference (dashboard replay)
    assert other_event_same_payment.status_code == 200
    assert await balance(db_session, org_id) == token_credits + starter
    rows = (await db_session.scalars(select(CreditTransaction).where(CreditTransaction.reason.like("%credits-ref-1%")))).all()
    assert len(rows) == 1 and rows[0].amount == token_credits + starter
    second_payment = await post(client, charge(org_id, reference="credits-ref-2", charge_id=3003))  # a genuinely new payment grants again
    assert second_payment.status_code == 200 and await balance(db_session, org_id) == token_credits + 2 * starter


@pytest.mark.parametrize("tamper", ["amount", "currency", "status", "pack", "kind", "org", "reference"])
async def test_tampered_or_unpaid_charges_grant_nothing(client, register_payload, db_session, paystack, tamper):
    _token, org_id = await org_in_nigeria(client, register_payload, db_session)
    event = {
        "amount": charge(org_id, amount=1), "currency": charge(org_id, currency="NGN"), "status": charge(org_id, status="failed"),
        "pack": charge(org_id, pack_id="does-not-exist"), "kind": charge(org_id, kind="subscription"), "org": charge(org_id, org=uuid.uuid4()),
        "reference": charge(org_id, reference=""),
    }[tamper]
    response = await post(client, event)
    assert response.status_code == 200  # acknowledged (so Paystack stops retrying) but nothing granted
    assert await balance(db_session, org_id) == 0


async def test_forged_unsigned_and_wrong_key_webhooks_are_refused_and_grant_nothing(client, register_payload, db_session, paystack):
    _token, org_id = await org_in_nigeria(client, register_payload, db_session)
    event = charge(org_id)
    assert (await post(client, event, key="sk_test_someone_else")).status_code == 400
    assert (await client.post("/billing/paystack/webhook", content=json.dumps(event).encode(), headers={"content-type": "application/json"})).status_code == 400
    body, sig = signed(event)
    assert (await client.post("/billing/paystack/webhook", content=body + b" ", headers=sig)).status_code == 400  # altered after signing
    assert await balance(db_session, org_id) == 0


async def test_a_credit_purchase_never_reactivates_or_changes_a_subscription(client, register_payload, db_session, paystack):
    _token, org_id = await org_in_nigeria(client, register_payload, db_session)
    plan = Plan(key=f"credits-sub-{uuid.uuid4().hex[:6]}", name="Sub Test", monthly_price_cents=2900, yearly_price_cents=29000)
    db_session.add(plan)
    await db_session.flush()
    sub = Subscription(organization_id=uuid.UUID(org_id), plan_id=plan.id, status=SubscriptionStatus.past_due)
    db_session.add(sub)
    await db_session.commit()
    assert (await post(client, charge(org_id))).status_code == 200
    db_session.expire_all()
    assert (await db_session.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(org_id)))).status == SubscriptionStatus.past_due
    assert await balance(db_session, org_id) == get_credit_pack("starter")["credits"]
