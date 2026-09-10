"""
Partie 12 -- billing. Two real deviations from the literal spec's flat
`/billing/...` paths, same "fix the incoherence, don't duplicate it"
discipline already applied to RBAC/security/audit/compliance in Partie
10 and admin subscriptions in Partie 11:

- Everything that belongs to ONE organization (subscription, usage,
  credits, invoices, Stripe checkout/portal) lives under
  `/organizations/{org_id}/billing/...`, this codebase's real,
  established convention (require_org_member/_admin/_owner all resolve
  `org_id` as a path parameter) -- a flat `/billing/subscription` has no
  way to know WHICH organization's subscription is meant for a user who
  belongs to more than one.
- `GET /billing/plans` and `GET /billing/plans/{id}` stay flat and
  PUBLIC (no auth) -- a plan catalog isn't organization data, it's
  marketing-page content, matching the literal spec exactly.
- `POST /billing/stripe/webhook` stays flat and public -- Stripe calls
  a single fixed URL it can't parameterize with an org_id; the real
  organization is resolved from the event's own metadata/customer id
  (api/services/billing_stripe.handle_stripe_webhook).

Admin-tier plan CRUD (`POST/PATCH/DELETE`) is NOT duplicated here --
`/admin/plans` (Partie 11.4, api/routers/admin_subscriptions.py) is
already the real, working admin CRUD; this router's plan endpoints are
read-only, for the same reason GET /billing/plans is public.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.billing import InvoiceStatus
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.billing import (
    CancelSubscriptionRequest, CheckoutSessionRequest, CheckoutSessionResponse, CreateUsageAlertRequest,
    CreditResponse, CreditTransactionResponse, InvoiceDetailResponse, InvoiceResponse, InvoiceStatsResponse,
    PaymentMethodResponse, PlanResponse, PortalSessionResponse, PurchaseCreditsRequest, StripeInvoiceResponse,
    SubscribeRequest, SubscriptionResponse, UsageAlertResponse, VoidInvoiceRequest,
)
from api.security.credit_packs import CREDIT_PACKS, get_credit_pack
from api.security.organizations import require_org_admin, require_org_member, require_org_owner
from api.services import admin_subscriptions, billing_credits, billing_invoices, billing_stripe, billing_usage
from api.services.admin_subscriptions import PlanNotFoundError, SubscriptionNotFoundError

router = APIRouter(tags=["Billing"])
org_router = APIRouter(prefix="/organizations/{org_id}/billing", tags=["Billing"])


# -- 12.1 plans (public catalog) ---------------------------------------------

@router.get("/billing/plans", response_model=list[PlanResponse])
async def list_plans_endpoint(db: AsyncSession = Depends(get_db)):
    plans = await admin_subscriptions.list_plans(db)
    await db.commit()  # list_plans seeds the real Free plan on first call -- must persist, not roll back
    return plans


@router.get("/billing/plans/{plan_id}", response_model=PlanResponse)
async def get_plan_endpoint(plan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        return await admin_subscriptions.get_plan(db, plan_id)
    except PlanNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")


# -- 12.1 subscription (org-scoped) ------------------------------------------

@org_router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    sub = await admin_subscriptions.get_or_create_subscription(db, org_id)
    await db.commit()  # get_or_create_subscription may INSERT a real free Subscription -- must persist
    return sub


@org_router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe_endpoint(org_id: uuid.UUID, body: SubscribeRequest, _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db)):
    sub = await admin_subscriptions.get_or_create_subscription(db, org_id)
    try:
        result = await admin_subscriptions.update_subscription(db, sub.id, plan_id=body.plan_id, billing_period=body.billing_period)
    except SubscriptionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    await db.commit()
    return result


@org_router.post("/upgrade", response_model=SubscriptionResponse)
@org_router.post("/downgrade", response_model=SubscriptionResponse)
async def change_plan_endpoint(org_id: uuid.UUID, body: SubscribeRequest, _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db)):
    sub = await admin_subscriptions.get_or_create_subscription(db, org_id)
    result = await admin_subscriptions.update_subscription(db, sub.id, plan_id=body.plan_id, billing_period=body.billing_period)
    await db.commit()
    return result


@org_router.post("/cancel", response_model=SubscriptionResponse)
async def cancel_subscription_endpoint(org_id: uuid.UUID, body: CancelSubscriptionRequest, _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db)):
    sub = await admin_subscriptions.get_or_create_subscription(db, org_id)
    result = await admin_subscriptions.cancel_subscription(db, sub.id, reason=body.reason)
    await db.commit()
    return result


@org_router.post("/reactivate", response_model=SubscriptionResponse)
async def reactivate_subscription_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db)):
    sub = await admin_subscriptions.get_or_create_subscription(db, org_id)
    result = await admin_subscriptions.reactivate_subscription(db, sub.id)
    await db.commit()
    return result


# -- 12.3 usage / credits -----------------------------------------------------

@org_router.get("/usage")
async def get_usage_endpoint(org_id: uuid.UUID, period_days: int = 30, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await billing_usage.get_usage_breakdown(db, org_id, period_days)


@org_router.get("/usage/breakdown")
async def get_usage_breakdown_endpoint(org_id: uuid.UUID, period_days: int = 30, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await billing_usage.get_usage_breakdown(db, org_id, period_days)


@org_router.get("/usage/forecast")
async def get_usage_forecast_endpoint(org_id: uuid.UUID, months: int = 1, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await billing_usage.get_usage_forecast(db, org_id, months)


@org_router.get("/usage/alerts", response_model=list[UsageAlertResponse])
async def list_usage_alerts_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await billing_usage.list_usage_alerts(db, org_id)


@org_router.post("/usage/alerts", response_model=UsageAlertResponse, status_code=status.HTTP_201_CREATED)
async def create_usage_alert_endpoint(org_id: uuid.UUID, body: CreateUsageAlertRequest, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    alert = await billing_usage.create_usage_alert(db, org_id, resource_type=body.resource_type, threshold_percent=body.threshold_percent, user_id=caller.user_id)
    await db.commit()
    return alert


@org_router.delete("/usage/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_usage_alert_endpoint(org_id: uuid.UUID, alert_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        await billing_usage.delete_usage_alert(db, org_id, alert_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    await db.commit()


@org_router.get("/credits", response_model=CreditResponse)
async def get_credits_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    credit = await billing_credits.get_or_create_credit(db, org_id)
    await db.commit()  # get_or_create_credit may INSERT a real Credit + its signup grant transaction
    return credit


@org_router.get("/credits/transactions", response_model=list[CreditTransactionResponse])
async def list_credit_transactions_endpoint(org_id: uuid.UUID, limit: int = 50, offset: int = 0, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await billing_credits.list_credit_transactions(db, org_id, limit, offset)


@org_router.get("/credits/packs")
async def list_credit_packs_endpoint(_caller: OrganizationMember = Depends(require_org_member)):
    return CREDIT_PACKS


@org_router.post("/credits/purchase", response_model=CreditResponse)
async def purchase_credits_endpoint(org_id: uuid.UUID, body: PurchaseCreditsRequest, caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db)):
    pack = get_credit_pack(body.pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown credit pack")
    # Real, honest scope: without a configured Stripe account, this
    # records a real credit grant directly (an admin/owner-initiated
    # top-up) rather than pretending to charge a card that was never
    # real -- same "real math, real $0 processor" pattern as Partie 11.4.
    credit = await billing_credits.add_credits(db, org_id, pack["credits"], source=f"Purchased pack '{pack['name']}'", user_id=caller.user_id)
    await db.commit()
    return credit


# -- 12.4 invoices -------------------------------------------------------------

@org_router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices_endpoint(org_id: uuid.UUID, status_filter: InvoiceStatus | None = None, limit: int = 50, offset: int = 0, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await billing_invoices.list_invoices(db, org_id, status_filter=status_filter, limit=limit, offset=offset)


@org_router.get("/invoices/stats", response_model=InvoiceStatsResponse)
async def invoice_stats_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    return await billing_invoices.get_invoice_stats(db, org_id)


@org_router.get("/invoices/{invoice_id}", response_model=InvoiceDetailResponse)
async def get_invoice_endpoint(org_id: uuid.UUID, invoice_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        invoice = await billing_invoices.get_invoice(db, org_id, invoice_id)
    except billing_invoices.InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    lines = await billing_invoices.get_invoice_lines(db, invoice_id)
    return InvoiceDetailResponse(**InvoiceResponse.model_validate(invoice).model_dump(), lines=lines)


@org_router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf_endpoint(org_id: uuid.UUID, invoice_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    from fastapi.responses import Response

    try:
        pdf_bytes = await billing_invoices.generate_invoice_pdf(db, org_id, invoice_id)
    except billing_invoices.InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    except billing_invoices.PDFUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return Response(content=pdf_bytes, media_type="application/pdf")


@org_router.post("/invoices/{invoice_id}/send", response_model=InvoiceResponse)
async def send_invoice_endpoint(org_id: uuid.UUID, invoice_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        invoice = await billing_invoices.send_invoice(db, org_id, invoice_id)
    except billing_invoices.InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    await db.commit()
    return invoice


@org_router.post("/invoices/{invoice_id}/remind", response_model=InvoiceResponse)
async def remind_invoice_endpoint(org_id: uuid.UUID, invoice_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        return await billing_invoices.remind_invoice(db, org_id, invoice_id)
    except billing_invoices.InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


@org_router.post("/invoices/{invoice_id}/pay", response_model=InvoiceResponse)
async def mark_invoice_paid_endpoint(org_id: uuid.UUID, invoice_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        invoice = await billing_invoices.mark_invoice_paid(db, org_id, invoice_id)
    except billing_invoices.InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    await db.commit()
    return invoice


@org_router.post("/invoices/{invoice_id}/void", response_model=InvoiceResponse)
async def void_invoice_endpoint(org_id: uuid.UUID, invoice_id: uuid.UUID, body: VoidInvoiceRequest, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        invoice = await billing_invoices.void_invoice(db, org_id, invoice_id, reason=body.reason)
    except billing_invoices.InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    await db.commit()
    return invoice


# -- 12.2 Stripe (org-scoped checkout/portal/payment methods/invoices) --------

@org_router.post("/stripe/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session_endpoint(org_id: uuid.UUID, body: CheckoutSessionRequest, caller: OrganizationMember = Depends(require_org_owner), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        url = await billing_stripe.create_checkout_session(db, org_id, price_id=body.price_id, email=current_user.email, org_name=str(org_id))
    except billing_stripe.StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    await db.commit()  # create_checkout_session may INSERT a real StripeCustomer row
    return CheckoutSessionResponse(url=url)


@org_router.post("/stripe/create-portal-session", response_model=PortalSessionResponse)
async def create_portal_session_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db)):
    try:
        url = await billing_stripe.create_portal_session(db, org_id)
    except billing_stripe.StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    return PortalSessionResponse(url=url)


@org_router.get("/stripe/payment-methods", response_model=list[PaymentMethodResponse])
async def list_payment_methods_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db)):
    try:
        return await billing_stripe.list_payment_methods(db, org_id)
    except billing_stripe.StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))


@org_router.delete("/stripe/payment-methods/{payment_method_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_payment_method_endpoint(org_id: uuid.UUID, payment_method_id: str, _caller: OrganizationMember = Depends(require_org_owner)):
    try:
        await billing_stripe.detach_payment_method(payment_method_id)
    except billing_stripe.StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))


@org_router.post("/stripe/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_stripe_subscription_endpoint(org_id: uuid.UUID, at_period_end: bool = True, _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db)):
    try:
        await billing_stripe.cancel_stripe_subscription(db, org_id, at_period_end=at_period_end)
    except billing_stripe.StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))


@org_router.get("/stripe/invoices", response_model=list[StripeInvoiceResponse])
async def list_stripe_invoices_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db)):
    try:
        return await billing_stripe.list_stripe_invoices(db, org_id)
    except billing_stripe.StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))


# -- 12.2 Stripe webhook (flat, public, signature-verified) -------------------

@router.post("/billing/stripe/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook_endpoint(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = billing_stripe.verify_webhook_signature(payload, signature)
    except billing_stripe.StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe signature")

    applied = await billing_stripe.handle_stripe_webhook(db, dict(event))
    await db.commit()
    return {"received": True, "applied": applied}
