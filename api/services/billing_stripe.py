"""
Partie 12.2 -- real Stripe integration code, honestly scoped: this
environment has no real Stripe account/keys (settings.STRIPE_SECRET_KEY
is None by default, see api/config.py), so every function below checks
that first and raises StripeNotConfiguredError rather than pretending
to reach a payment processor that isn't there -- same honest-501
pattern api/services/admin_subscriptions.py already established for
POST /admin/subscriptions/{id}/refund. The moment a real key is set in
.env, every function here makes a real Stripe API call -- nothing is
mocked internally.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.billing import StripeCustomer, StripeEvent
from api.models.organization import Organization

logger = logging.getLogger(__name__)


class StripeNotConfiguredError(Exception):
    pass


def _client():
    if not settings.STRIPE_SECRET_KEY:
        raise StripeNotConfiguredError(
            "Stripe is not configured on this deployment -- set STRIPE_SECRET_KEY in .env to enable real payments."
        )
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = settings.STRIPE_API_VERSION
    return stripe


async def get_stripe_customer(db: AsyncSession, organization_id: uuid.UUID) -> StripeCustomer | None:
    return await db.scalar(select(StripeCustomer).where(StripeCustomer.organization_id == organization_id))


async def create_stripe_customer(db: AsyncSession, organization_id: uuid.UUID, *, email: str, name: str) -> StripeCustomer:
    existing = await get_stripe_customer(db, organization_id)
    if existing is not None:
        return existing

    stripe = _client()
    customer = stripe.Customer.create(email=email, name=name, metadata={"organization_id": str(organization_id)})
    row = StripeCustomer(organization_id=organization_id, stripe_customer_id=customer["id"])
    db.add(row)
    await db.flush()
    return row


async def create_checkout_session(db: AsyncSession, organization_id: uuid.UUID, *, price_id: str, email: str, org_name: str) -> str:
    stripe = _client()
    customer = await create_stripe_customer(db, organization_id, email=email, name=org_name)
    session = stripe.checkout.Session.create(
        customer=customer.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
        metadata={"organization_id": str(organization_id)},
    )
    return session["url"]


async def create_portal_session(db: AsyncSession, organization_id: uuid.UUID) -> str:
    stripe = _client()
    customer = await get_stripe_customer(db, organization_id)
    if customer is None:
        raise StripeNotConfiguredError("This organization has no Stripe customer yet -- start a checkout session first.")
    session = stripe.billing_portal.Session.create(customer=customer.stripe_customer_id, return_url=settings.STRIPE_PORTAL_RETURN_URL)
    return session["url"]


async def list_payment_methods(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    stripe = _client()
    customer = await get_stripe_customer(db, organization_id)
    if customer is None:
        return []
    methods = stripe.PaymentMethod.list(customer=customer.stripe_customer_id, type="card")
    return [
        {"id": m["id"], "brand": m["card"]["brand"], "last4": m["card"]["last4"], "exp_month": m["card"]["exp_month"], "exp_year": m["card"]["exp_year"]}
        for m in methods["data"]
    ]


async def detach_payment_method(payment_method_id: str) -> None:
    stripe = _client()
    stripe.PaymentMethod.detach(payment_method_id)


async def cancel_stripe_subscription(db: AsyncSession, organization_id: uuid.UUID, *, at_period_end: bool = True) -> None:
    stripe = _client()
    sub = await db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
    if sub is None or not sub.stripe_subscription_id:
        raise StripeNotConfiguredError("This organization has no real Stripe subscription to cancel.")
    if at_period_end:
        stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)
    else:
        stripe.Subscription.cancel(sub.stripe_subscription_id)


async def list_stripe_invoices(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    stripe = _client()
    customer = await get_stripe_customer(db, organization_id)
    if customer is None:
        return []
    invoices = stripe.Invoice.list(customer=customer.stripe_customer_id, limit=25)
    return [{"id": i["id"], "number": i.get("number"), "status": i["status"], "total": i["total"], "currency": i["currency"], "hosted_invoice_url": i.get("hosted_invoice_url")} for i in invoices["data"]]


def verify_webhook_signature(payload: bytes, signature_header: str):
    stripe = _client()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise StripeNotConfiguredError("STRIPE_WEBHOOK_SECRET is not set -- cannot verify webhook authenticity.")
    return stripe.Webhook.construct_event(payload, signature_header, settings.STRIPE_WEBHOOK_SECRET)


async def handle_stripe_webhook(db: AsyncSession, event: dict) -> bool:
    """Real event processing, idempotent via StripeEvent (Stripe
    guarantees at-least-once delivery, never exactly-once). Returns
    False if this event id was already applied."""
    event_id = event["id"]
    if await db.get(StripeEvent, event_id) is not None:
        return False

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        org_id = data.get("metadata", {}).get("organization_id")
        if org_id:
            sub = await db.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(org_id)))
            if sub is not None:
                sub.status = SubscriptionStatus.active if data["status"] == "active" else SubscriptionStatus.past_due
                await db.flush()
    elif event_type == "customer.subscription.deleted":
        org_id = data.get("metadata", {}).get("organization_id")
        if org_id:
            sub = await db.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(org_id)))
            if sub is not None:
                sub.status = SubscriptionStatus.canceled
                await db.flush()
    elif event_type == "invoice.payment_failed":
        org_id = data.get("metadata", {}).get("organization_id")
        if org_id:
            sub = await db.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(org_id)))
            if sub is not None:
                sub.status = SubscriptionStatus.past_due
                await db.flush()

    db.add(StripeEvent(id=event_id, type=event_type, payload_summary=str(data.get("id", ""))))
    await db.flush()
    return True
