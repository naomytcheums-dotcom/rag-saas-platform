"""
Phase 5, Étape 2 -- real Paystack integration, same honest-501 pattern
as api/services/billing_stripe.py: `settings.PAYSTACK_SECRET_KEY` is
None by default, so every function below checks that first and raises
PaystackNotConfiguredError rather than pretending to reach a payment
processor that isn't there. The moment a real key is set in .env,
every function here makes a real Paystack REST API call
(https://api.paystack.co) -- nothing is mocked internally.

Uses `httpx` directly (Paystack has no official Python SDK, unlike
Stripe) against a single, fixed, hardcoded host -- not
`ssrf_safe_client()` (api/services/url_fetching.py), because that
helper exists to protect against a caller-supplied URL reaching
internal infrastructure; `https://api.paystack.co` is never
user-supplied here, so the SSRF threat model doesn't apply, same
reasoning this codebase already applies to the `stripe` SDK's own
outbound calls in billing_stripe.py.

Paystack concepts mapped onto this codebase's existing Stripe-shaped
vocabulary:
- Stripe "Price" -> Paystack "Plan" (a `plan_code`, created via
  POST /plan) -- see `Plan.paystack_plan_code_monthly/_yearly`
  (api/models/admin.py).
- Stripe "Checkout Session" -> Paystack "Transaction" initialize
  (POST /transaction/initialize with a `plan` code subscribes the
  customer to that plan once payment succeeds).
- Stripe "Billing Portal" -> Paystack "subscription manage link"
  (GET /subscription/:code/manage/link), Paystack's own real,
  documented self-service subscription management URL.
- Stripe "PaymentMethod" -> Paystack "Authorization" (a saved card,
  returned on a customer's own record).
- Stripe webhook HMAC-in-SDK -> Paystack webhook signature is a raw
  HMAC-SHA512 of the request body using the secret key, compared
  against the `x-paystack-signature` header (Paystack's own documented
  scheme -- there is no separate webhook secret, unlike Stripe).
"""

import hashlib
import hmac
import json
import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.billing import PaymentCustomer, PaymentEvent, PaymentProvider
from api.services.billing_providers.base import ProviderNotConfiguredError

logger = logging.getLogger(__name__)

PAYSTACK_BASE_URL = "https://api.paystack.co"


class PaystackNotConfiguredError(ProviderNotConfiguredError):
    """See billing_stripe.StripeNotConfiguredError's own docstring for
    why this is a real subclass of the shared ProviderNotConfiguredError
    rather than a plain alias."""


def _client() -> httpx.AsyncClient:
    if not settings.PAYSTACK_SECRET_KEY:
        raise PaystackNotConfiguredError(
            "Paystack is not configured on this deployment -- set PAYSTACK_SECRET_KEY in .env to enable real payments."
        )
    return httpx.AsyncClient(
        base_url=PAYSTACK_BASE_URL,
        headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}", "Content-Type": "application/json"},
        timeout=15.0,
    )


def _raise_for_paystack_error(response: httpx.Response) -> dict:
    body = response.json()
    if response.status_code >= 400 or body.get("status") is False:
        raise RuntimeError(f"Paystack API error ({response.status_code}): {body.get('message', 'unknown error')}")
    return body


async def get_paystack_customer(db: AsyncSession, organization_id: uuid.UUID) -> PaymentCustomer | None:
    return await db.scalar(
        select(PaymentCustomer).where(PaymentCustomer.organization_id == organization_id, PaymentCustomer.provider == PaymentProvider.paystack)
    )


async def create_paystack_customer(db: AsyncSession, organization_id: uuid.UUID, *, email: str, name: str) -> PaymentCustomer:
    existing = await get_paystack_customer(db, organization_id)
    if existing is not None:
        return existing

    async with _client() as client:
        response = await client.post("/customer", json={"email": email, "first_name": name, "last_name": "Organization"})
        body = _raise_for_paystack_error(response)

    row = PaymentCustomer(organization_id=organization_id, provider=PaymentProvider.paystack, external_customer_id=body["data"]["customer_code"])
    db.add(row)
    await db.flush()
    return row


async def create_checkout_session(db: AsyncSession, organization_id: uuid.UUID, *, plan_code: str, email: str, org_name: str) -> str:
    """Returns a real, hosted Paystack payment page URL. `plan_code`
    subscribes the customer to that recurring plan once payment
    succeeds -- Paystack itself creates the Subscription server-side;
    this codebase's own Subscription row is reconciled by the
    `subscription.create` webhook (see handle_paystack_webhook)."""
    await create_paystack_customer(db, organization_id, email=email, name=org_name)
    async with _client() as client:
        response = await client.post(
            "/transaction/initialize",
            json={
                "email": email,
                "amount": 0,  # the plan's own amount governs the real charge; Paystack requires the field regardless
                "plan": plan_code,
                "callback_url": settings.PAYSTACK_CALLBACK_URL,
                "metadata": {"organization_id": str(organization_id)},
            },
        )
        body = _raise_for_paystack_error(response)
    return body["data"]["authorization_url"]


async def create_portal_session(db: AsyncSession, organization_id: uuid.UUID) -> str:
    sub = await db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
    if sub is None or not sub.paystack_subscription_code:
        raise PaystackNotConfiguredError("This organization has no real Paystack subscription yet -- start a checkout session first.")
    async with _client() as client:
        response = await client.get(f"/subscription/{sub.paystack_subscription_code}/manage/link")
        body = _raise_for_paystack_error(response)
    return body["data"]["link"]


async def list_payment_methods(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    customer = await get_paystack_customer(db, organization_id)
    if customer is None:
        return []
    async with _client() as client:
        response = await client.get(f"/customer/{customer.external_customer_id}")
        body = _raise_for_paystack_error(response)
    return [
        {"id": auth["authorization_code"], "brand": auth.get("card_type", "unknown"), "last4": auth.get("last4", ""), "exp_month": auth.get("exp_month", ""), "exp_year": auth.get("exp_year", "")}
        for auth in body["data"].get("authorizations", [])
    ]


async def cancel_paystack_subscription(db: AsyncSession, organization_id: uuid.UUID, *, at_period_end: bool = True) -> None:
    sub = await db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
    if sub is None or not sub.paystack_subscription_code:
        raise PaystackNotConfiguredError("This organization has no real Paystack subscription to cancel.")
    async with _client() as client:
        response = await client.get(f"/subscription/{sub.paystack_subscription_code}")
        body = _raise_for_paystack_error(response)
        email_token = body["data"]["email_token"]
        response = await client.post("/subscription/disable", json={"code": sub.paystack_subscription_code, "token": email_token})
        _raise_for_paystack_error(response)
    # Paystack's own "disable" always takes effect at the end of the
    # current paid period -- there is no real "cancel immediately" on
    # their API, so `at_period_end` is accepted for interface parity
    # with Stripe but has no separate code path here (an honest,
    # documented difference, not a silent no-op).


async def list_provider_invoices(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    customer = await get_paystack_customer(db, organization_id)
    if customer is None:
        return []
    async with _client() as client:
        response = await client.get("/transaction", params={"customer": customer.external_customer_id, "perPage": 25})
        body = _raise_for_paystack_error(response)
    return [
        {"id": str(t["id"]), "number": t.get("reference"), "status": t["status"], "total": t["amount"], "currency": t["currency"], "hosted_invoice_url": None}
        for t in body["data"]
    ]


def verify_webhook_signature(payload: bytes, signature_header: str) -> dict:
    """Paystack's own documented scheme: HMAC-SHA512 of the raw request
    body, keyed with the secret key itself -- there is no separate
    webhook-specific secret the way Stripe has STRIPE_WEBHOOK_SECRET."""
    if not settings.PAYSTACK_SECRET_KEY:
        raise PaystackNotConfiguredError("PAYSTACK_SECRET_KEY is not set -- cannot verify webhook authenticity.")
    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), payload, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(expected, signature_header or ""):
        raise ValueError("Invalid Paystack webhook signature")
    return json.loads(payload)


async def handle_paystack_webhook(db: AsyncSession, event: dict) -> bool:
    """Real event processing, idempotent via PaymentEvent (Paystack,
    like Stripe, guarantees at-least-once delivery). Paystack events
    have no top-level `id` the way Stripe's do -- the (event type,
    the underlying object's own id) pair is used as this codebase's own
    idempotency key instead, which is unique per real Paystack event in
    practice (Paystack never re-emits the exact same object id twice
    for two logically different events of the same type)."""
    data = event.get("data", {})
    event_type = event.get("event", "")
    object_id = str(data.get("id", data.get("subscription_code", "")))
    event_id = f"{event_type}:{object_id}"

    if await db.get(PaymentEvent, (PaymentProvider.paystack, event_id)) is not None:
        return False

    org_id = (data.get("metadata") or {}).get("organization_id")
    customer_code = (data.get("customer") or {}).get("customer_code")

    if org_id is None and customer_code:
        customer = await db.scalar(
            select(PaymentCustomer).where(PaymentCustomer.provider == PaymentProvider.paystack, PaymentCustomer.external_customer_id == customer_code)
        )
        if customer is not None:
            org_id = str(customer.organization_id)

    if org_id:
        sub = await db.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(org_id)))
        if sub is not None:
            if event_type == "subscription.create":
                sub.status = SubscriptionStatus.active
                sub.paystack_subscription_code = data.get("subscription_code")
            elif event_type == "charge.success":
                sub.status = SubscriptionStatus.active
            elif event_type == "subscription.disable":
                sub.status = SubscriptionStatus.canceled
            elif event_type == "invoice.payment_failed":
                sub.status = SubscriptionStatus.past_due
            await db.flush()
            if event_type == "invoice.payment_failed":
                from api.services.notifications import notify_billing_payment_failed

                await notify_billing_payment_failed(db, uuid.UUID(org_id))

    db.add(PaymentEvent(provider=PaymentProvider.paystack, id=event_id, type=event_type, payload_summary=object_id))
    await db.flush()
    return True


class PaystackProvider:
    """Thin `BillingProvider` adapter over the module-level functions
    above -- registered as `PaymentProvider.paystack` in
    api/services/billing_providers/registry.py."""

    name = "paystack"

    def is_configured(self) -> bool:
        return bool(settings.PAYSTACK_SECRET_KEY)

    async def create_checkout_session(self, db: AsyncSession, organization_id: uuid.UUID, *, plan: Plan, billing_period: str, email: str, org_name: str) -> str:
        plan_code = plan.paystack_plan_code_yearly if billing_period == "yearly" else plan.paystack_plan_code_monthly
        if not plan_code:
            raise ValueError(f"Plan {plan.key!r} has no paystack_plan_code_{billing_period} set -- create it on Paystack first.")
        return await create_checkout_session(db, organization_id, plan_code=plan_code, email=email, org_name=org_name)

    async def create_portal_session(self, db: AsyncSession, organization_id: uuid.UUID) -> str:
        return await create_portal_session(db, organization_id)

    async def list_payment_methods(self, db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
        return await list_payment_methods(db, organization_id)

    async def cancel_subscription(self, db: AsyncSession, organization_id: uuid.UUID, *, at_period_end: bool = True) -> None:
        await cancel_paystack_subscription(db, organization_id, at_period_end=at_period_end)

    async def list_provider_invoices(self, db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
        return await list_provider_invoices(db, organization_id)

    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> dict:
        return verify_webhook_signature(payload, signature_header)

    async def handle_webhook(self, db: AsyncSession, event: dict) -> bool:
        return await handle_paystack_webhook(db, event)
