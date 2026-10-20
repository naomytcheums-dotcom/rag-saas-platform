"""Paystack REST calls of api/services/billing_paystack.py against a LOCAL FAKE Paystack API (tests/vendor_fakes.py), not the real service: requests (path, body,
auth), reading of the answers, error handling, signature verification and the provider adapter. The webhook state machine has its own tests (test_p2_bill013_paystack_credit_pack.py,
tests/test_billing_plans_limits_postgres.py)."""

import hashlib
import hmac
import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vendor_fakes import FakeVendor, Resp  # noqa: E402

from api.config import settings  # noqa: E402
from api.models.admin import Plan, Subscription, SubscriptionStatus  # noqa: E402
from api.models.billing import PaymentCustomer, PaymentProvider  # noqa: E402
from api.models.organization import Organization  # noqa: E402
from api.security.credit_packs import CREDIT_PACKS  # noqa: E402
from api.services import billing_paystack as paystack  # noqa: E402


@pytest.fixture
def vendor(monkeypatch):
    with FakeVendor() as fake:
        monkeypatch.setattr(settings, "PAYSTACK_API_BASE_URL", fake.url)
        monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "sk_test_contract")
        yield fake


@pytest.fixture
async def org(db_session):
    organization = Organization(name="Pay", slug=f"pay-{uuid.uuid4().hex[:8]}")
    db_session.add(organization)
    await db_session.flush()
    return organization.id


async def _with_subscription(db_session, org_id, code="SUB_123") -> Plan:
    plan = Plan(key=f"p{uuid.uuid4().hex[:8]}", name="Plan", monthly_price_cents=1000, paystack_plan_code_monthly="PLN_m", paystack_plan_code_yearly="PLN_y")
    db_session.add(plan)
    await db_session.flush()
    db_session.add(Subscription(organization_id=org_id, plan_id=plan.id, status=SubscriptionStatus.active, paystack_subscription_code=code))
    await db_session.flush()
    return plan


async def test_without_a_secret_key_every_call_is_a_clear_not_configured_error(db_session, org, monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", None)
    with pytest.raises(paystack.PaystackNotConfiguredError):
        await paystack.create_paystack_customer(db_session, org, email="a@b.test", name="Pay")
    with pytest.raises(paystack.PaystackNotConfiguredError):
        await paystack.create_credit_pack_checkout_session(db_session, org, pack=CREDIT_PACKS[0], email="a@b.test", org_name="Pay")
    with pytest.raises(paystack.PaystackNotConfiguredError):
        paystack.verify_webhook_signature(b"{}", "sig")
    assert paystack.PaystackProvider().is_configured() is False


async def test_a_customer_is_created_once_with_the_secret_key_as_bearer(db_session, org, vendor):
    vendor.on("POST", "/customer", Resp(200, {"status": True, "data": {"customer_code": "CUS_abc"}}))

    first = await paystack.create_paystack_customer(db_session, org, email="owner@example.test", name="Pay")
    again = await paystack.create_paystack_customer(db_session, org, email="owner@example.test", name="Pay")

    assert first.external_customer_id == "CUS_abc" and again.id == first.id and first.provider == PaymentProvider.paystack
    (request,) = vendor.calls("POST", "/customer")  # the second call found the stored customer
    assert request.headers["authorization"] == "Bearer sk_test_contract"
    assert request.json() == {"email": "owner@example.test", "first_name": "Pay", "last_name": "Organization"}
    assert (await paystack.get_paystack_customer(db_session, org)).id == first.id


async def test_a_subscription_checkout_returns_the_hosted_page_and_names_the_plan_and_organization(db_session, org, vendor):
    vendor.on("POST", "/customer", Resp(200, {"status": True, "data": {"customer_code": "CUS_abc"}}))
    vendor.on("POST", "/transaction/initialize", Resp(200, {"status": True, "data": {"authorization_url": "https://checkout.paystack.test/abc"}}))

    url = await paystack.create_checkout_session(db_session, org, plan_code="PLN_m", email="owner@example.test", org_name="Pay")

    assert url == "https://checkout.paystack.test/abc"
    body = vendor.calls("POST", "/transaction/initialize")[0].json()
    assert body["plan"] == "PLN_m" and body["metadata"] == {"organization_id": str(org)} and body["email"] == "owner@example.test"


async def test_a_credit_pack_checkout_is_a_one_off_priced_transaction_with_a_server_made_reference(db_session, org, vendor):
    vendor.on("POST", "/customer", Resp(200, {"status": True, "data": {"customer_code": "CUS_abc"}}))
    vendor.on("POST", "/transaction/initialize", Resp(200, {"status": True, "data": {"authorization_url": "https://checkout.paystack.test/pack"}}))
    pack = CREDIT_PACKS[0]

    assert await paystack.create_credit_pack_checkout_session(db_session, org, pack=pack, email="o@example.test", org_name="Pay") == "https://checkout.paystack.test/pack"

    body = vendor.calls("POST", "/transaction/initialize")[0].json()
    assert body["amount"] == pack["price_cents"] and body["currency"] == settings.CREDIT_PACK_CURRENCY.upper()
    assert body["reference"].startswith("credits-") and "plan" not in body
    assert body["metadata"] == {"organization_id": str(org), "kind": "credit_pack", "pack_id": pack["id"]}


@pytest.mark.parametrize("response", [Resp(400, {"status": False, "message": "Invalid key"}), Resp(200, {"status": False, "message": "Duplicate customer"})])
async def test_paystack_errors_become_runtime_errors_with_their_message(db_session, org, vendor, response):
    vendor.on("POST", "/customer", response)

    with pytest.raises(RuntimeError, match="Paystack API error"):
        await paystack.create_paystack_customer(db_session, org, email="o@example.test", name="Pay")


async def test_the_portal_link_needs_a_paystack_subscription_and_comes_from_its_manage_endpoint(db_session, org, vendor):
    with pytest.raises(paystack.PaystackNotConfiguredError, match="no real Paystack subscription"):
        await paystack.create_portal_session(db_session, org)
    await _with_subscription(db_session, org)
    vendor.on("GET", "/subscription/SUB_123/manage/link", Resp(200, {"status": True, "data": {"link": "https://paystack.test/manage/xyz"}}))

    assert await paystack.create_portal_session(db_session, org) == "https://paystack.test/manage/xyz"


async def test_saved_cards_are_read_from_the_customer_record(db_session, org, vendor):
    assert await paystack.list_payment_methods(db_session, org) == []  # no customer yet
    db_session.add(PaymentCustomer(organization_id=org, provider=PaymentProvider.paystack, external_customer_id="CUS_abc"))
    await db_session.flush()
    vendor.on("GET", "/customer/CUS_abc", Resp(200, {"status": True, "data": {"authorizations": [
        {"authorization_code": "AUTH_1", "card_type": "visa", "last4": "4081", "exp_month": "12", "exp_year": "2030"}, {"authorization_code": "AUTH_2"}]}}))

    methods = await paystack.list_payment_methods(db_session, org)

    assert methods == [
        {"id": "AUTH_1", "brand": "visa", "last4": "4081", "exp_month": "12", "exp_year": "2030"},
        {"id": "AUTH_2", "brand": "unknown", "last4": "", "exp_month": "", "exp_year": ""},
    ]


async def test_cancelling_reads_the_email_token_then_disables_the_subscription(db_session, org, vendor):
    with pytest.raises(paystack.PaystackNotConfiguredError, match="no real Paystack subscription to cancel"):
        await paystack.cancel_paystack_subscription(db_session, org)
    await _with_subscription(db_session, org)
    vendor.on("GET", "/subscription/SUB_123", Resp(200, {"status": True, "data": {"email_token": "tok-9"}}))
    vendor.on("POST", "/subscription/disable", Resp(200, {"status": True, "message": "Subscription disabled successfully"}))

    await paystack.cancel_paystack_subscription(db_session, org)

    assert vendor.calls("POST", "/subscription/disable")[0].json() == {"code": "SUB_123", "token": "tok-9"}


async def test_a_failed_disable_is_reported_not_swallowed(db_session, org, vendor):
    await _with_subscription(db_session, org)
    vendor.on("GET", "/subscription/SUB_123", Resp(200, {"status": True, "data": {"email_token": "tok-9"}}))
    vendor.on("POST", "/subscription/disable", Resp(400, {"status": False, "message": "Subscription already inactive"}))

    with pytest.raises(RuntimeError, match="already inactive"):
        await paystack.cancel_paystack_subscription(db_session, org)


async def test_provider_invoices_are_the_customers_transactions(db_session, org, vendor):
    assert await paystack.list_provider_invoices(db_session, org) == []
    db_session.add(PaymentCustomer(organization_id=org, provider=PaymentProvider.paystack, external_customer_id="CUS_abc"))
    await db_session.flush()
    vendor.on("GET", "/transaction", Resp(200, {"status": True, "data": [{"id": 77, "reference": "ref-77", "status": "success", "amount": 5000, "currency": "NGN"}]}))

    invoices = await paystack.list_provider_invoices(db_session, org)

    assert invoices == [{"id": "77", "number": "ref-77", "status": "success", "total": 5000, "currency": "NGN", "hosted_invoice_url": None}]
    assert vendor.calls("GET", "/transaction")[0].query == {"customer": ["CUS_abc"], "perPage": ["25"]}


def test_the_webhook_signature_is_an_hmac_sha512_of_the_raw_body(vendor):
    payload = json.dumps({"event": "charge.success", "data": {"id": 1}}).encode()
    good = hmac.new(b"sk_test_contract", payload, hashlib.sha512).hexdigest()

    assert paystack.verify_webhook_signature(payload, good)["event"] == "charge.success"
    for bad in ("", "0" * 128, good[:-1] + ("0" if good[-1] != "0" else "1")):
        with pytest.raises(ValueError, match="Invalid Paystack webhook signature"):
            paystack.verify_webhook_signature(payload, bad)
    with pytest.raises(ValueError):
        paystack.verify_webhook_signature(payload + b" ", good)  # the body must be exactly what was signed


async def test_the_provider_adapter_picks_the_plan_code_of_the_billing_period(db_session, org, vendor):
    vendor.on("POST", "/customer", Resp(200, {"status": True, "data": {"customer_code": "CUS_abc"}}))
    vendor.on("POST", "/transaction/initialize", Resp(200, {"status": True, "data": {"authorization_url": "https://checkout.paystack.test/x"}}))
    provider = paystack.PaystackProvider()
    plan = Plan(key="adapter", name="A", paystack_plan_code_monthly="PLN_m", paystack_plan_code_yearly="PLN_y")
    no_codes = Plan(key="nocodes", name="N")

    assert provider.is_configured() is True and provider.name == "paystack"
    await provider.create_checkout_session(db_session, org, plan=plan, billing_period="yearly", email="o@example.test", org_name="Pay")
    await provider.create_checkout_session(db_session, org, plan=plan, billing_period="monthly", email="o@example.test", org_name="Pay")
    assert [r.json()["plan"] for r in vendor.calls("POST", "/transaction/initialize")] == ["PLN_y", "PLN_m"]
    with pytest.raises(ValueError, match="no paystack_plan_code_yearly"):
        await provider.create_checkout_session(db_session, org, plan=no_codes, billing_period="yearly", email="o@example.test", org_name="Pay")


async def test_the_provider_adapter_delegates_portal_cards_cancel_and_invoices(db_session, org, vendor):
    await _with_subscription(db_session, org)
    db_session.add(PaymentCustomer(organization_id=org, provider=PaymentProvider.paystack, external_customer_id="CUS_abc"))
    await db_session.flush()
    vendor.on("GET", "/subscription/SUB_123/manage/link", Resp(200, {"status": True, "data": {"link": "https://paystack.test/manage"}}))
    vendor.on("GET", "/customer/CUS_abc", Resp(200, {"status": True, "data": {"authorizations": []}}))
    vendor.on("GET", "/subscription/SUB_123", Resp(200, {"status": True, "data": {"email_token": "t"}}))
    vendor.on("POST", "/subscription/disable", Resp(200, {"status": True}))
    vendor.on("GET", "/transaction", Resp(200, {"status": True, "data": []}))
    provider = paystack.PaystackProvider()

    assert await provider.create_portal_session(db_session, org) == "https://paystack.test/manage"
    assert await provider.list_payment_methods(db_session, org) == []
    await provider.cancel_subscription(db_session, org)
    assert await provider.list_provider_invoices(db_session, org) == []
    assert vendor.calls("POST", "/subscription/disable")
