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

import datetime as dt
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_current_user, get_db
from api.models.admin import Plan, SubscriptionStatus
from api.models.audit_log import AuditAction
from api.models.billing import InvoiceStatus
from api.models.organization import Organization, OrganizationMember
from api.models.user import User, UserRole
from api.schemas.billing import (
    BillingCountryResponse, BillingCountryUpdateRequest, BillingProviderResponse, CancelSubscriptionRequest,
    CheckoutSessionRequest, CheckoutSessionResponse, CreateUsageAlertRequest, CreditResponse,
    CreditTransactionResponse, DisplayCurrencyResponse, InvoiceDetailResponse, InvoiceResponse, InvoiceStatsResponse, PaymentMethodResponse,
    PlanResponse, PortalSessionResponse, ProviderInvoiceResponse, PurchaseCreditsRequest, StripeInvoiceResponse,
    SubscribeRequest, SubscriptionResponse, UnifiedCheckoutRequest, UsageAlertResponse, VoidInvoiceRequest,
)
from api.security.audit_log import log_audit_action
from api.security.logging_correlation import get_request_id
from api.security.permissions import require_permission
from api.security.credit_packs import CREDIT_PACKS, get_credit_pack
from api.security.organizations import require_org_admin, require_org_member, require_org_owner
from api.services import admin_subscriptions, billing_credits, billing_invoices, billing_stripe, billing_usage
from api.services.display_currency import resolve_display_currency
from api.services.admin_subscriptions import PlanNotFoundError, SubscriptionNotFoundError
from api.services.billing_providers.base import ProviderNotConfiguredError
from api.services.billing_providers.registry import resolve_provider_for_organization
from api.utils import MAX_PAGE_SIZE, client_ip

router = APIRouter(tags=["Billing"])
org_router = APIRouter(prefix="/organizations/{org_id}/billing", tags=["Billing"])
logger = logging.getLogger(__name__)


async def _audit_billing(db: AsyncSession, request: Request, caller: OrganizationMember, org_id: uuid.UUID, action: AuditAction, **metadata) -> None:
    """V9: every state-changing billing action of an organization (plan, cancellation, credits, country, payment method) leaves an audit row
    scoped to the organization, written in the same transaction as the change."""
    await log_audit_action(
        db, user_id=caller.user_id, action=action, ip=client_ip(request), user_agent=request.headers.get("user-agent"), success=True,
        organization_id=org_id, resource_type="billing", resource_id=str(org_id), metadata={"request_id": get_request_id(), **metadata},
    )


# -- 12.1 plans (public catalog) ---------------------------------------------

@router.get("/billing/display-currency", response_model=DisplayCurrencyResponse)
async def display_currency_endpoint(request: Request, country: str | None = Query(None, min_length=2, max_length=2)):
    """Public. The currency (and a language suggestion) for the visitor, from an explicit `country` hint, else their IP, else their browser language."""
    return await resolve_display_currency(accept_language=request.headers.get("accept-language"), ip=client_ip(request), country_hint=country)


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
async def get_subscription_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:read")), db: AsyncSession = Depends(get_db)):
    sub = await admin_subscriptions.get_or_create_subscription(db, org_id)
    await db.commit()  # get_or_create_subscription may INSERT a real free Subscription -- must persist
    return sub


def _monthly_equivalent_cents(plan) -> int:
    return max(plan.monthly_price_cents or 0, -(-(plan.yearly_price_cents or 0) // 12))


async def _enforce_no_free_paid_plan(db: AsyncSession, sub, body: SubscribeRequest) -> None:
    """BILL-001 -- subscribe/upgrade/downgrade only write `Subscription.plan_id`; they never charge anything. A paid
    plan must therefore come from a confirmed payment (the provider's verified webhook after a checkout), never from
    these routes. They stay usable for a free plan, a strictly cheaper plan (a downgrade) and a no-op re-selection of
    the current plan. `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS` is the explicit opt-out for self-hosted/dev instances."""
    if settings.BILLING_ALLOW_SELF_SERVICE_PAID_PLANS:
        return
    try:
        target = await admin_subscriptions.get_plan(db, body.plan_id)
    except PlanNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    target_cost = _monthly_equivalent_cents(target)
    if target_cost <= 0:
        return
    if sub.plan_id == target.id and sub.billing_period == body.billing_period:
        return
    current = await db.get(Plan, sub.plan_id) if sub.plan_id else None
    if current is not None and target_cost < _monthly_equivalent_cents(current):
        return
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail="A paid plan can only be activated through a confirmed payment: start a checkout (POST .../billing/checkout) instead of changing the plan directly",
    )


@org_router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe_endpoint(org_id: uuid.UUID, body: SubscribeRequest, request: Request, caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    sub = await admin_subscriptions.get_or_create_subscription(db, org_id)
    before = {"plan_id": str(sub.plan_id), "billing_period": sub.billing_period}
    await _enforce_no_free_paid_plan(db, sub, body)
    try:
        result = await admin_subscriptions.update_subscription(db, sub.id, plan_id=body.plan_id, billing_period=body.billing_period)
    except SubscriptionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    except PlanNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    await _audit_billing(db, request, caller, org_id, AuditAction.BILLING_PLAN_CHANGED, operation="subscribe", before=before, after={"plan_id": str(result.plan_id), "billing_period": result.billing_period})
    await db.commit()
    return result


@org_router.post("/upgrade", response_model=SubscriptionResponse)
@org_router.post("/downgrade", response_model=SubscriptionResponse)
async def change_plan_endpoint(org_id: uuid.UUID, body: SubscribeRequest, request: Request, caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    sub = await admin_subscriptions.get_or_create_subscription(db, org_id)
    before = {"plan_id": str(sub.plan_id), "billing_period": sub.billing_period}
    await _enforce_no_free_paid_plan(db, sub, body)
    try:
        result = await admin_subscriptions.update_subscription(db, sub.id, plan_id=body.plan_id, billing_period=body.billing_period)
    except PlanNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    await _audit_billing(db, request, caller, org_id, AuditAction.BILLING_PLAN_CHANGED, operation="change", before=before, after={"plan_id": str(result.plan_id), "billing_period": result.billing_period})
    await db.commit()
    return result


@org_router.post("/cancel", response_model=SubscriptionResponse)
async def cancel_subscription_endpoint(org_id: uuid.UUID, body: CancelSubscriptionRequest, request: Request, caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    sub = await admin_subscriptions.get_or_create_subscription(db, org_id)
    if sub.stripe_subscription_id or sub.paystack_subscription_code:
        # BILL-006: a provider-managed subscription is cancelled at the provider first (at period end), otherwise the provider
        # keeps charging. Access runs until the period ends; the provider's webhook then moves the subscription to canceled.
        await _cancel_at_provider(db, org_id, sub)
        sub.canceled_at = dt.datetime.now(dt.timezone.utc)
        sub.cancel_reason = body.reason
        await _audit_billing(db, request, caller, org_id, AuditAction.BILLING_SUBSCRIPTION_CANCELED, via="provider", at_period_end=True)
        await db.commit()
        return sub
    result = await admin_subscriptions.cancel_subscription(db, sub.id, reason=body.reason)
    await _audit_billing(db, request, caller, org_id, AuditAction.BILLING_SUBSCRIPTION_CANCELED, via="local")
    await db.commit()
    return result


async def _cancel_at_provider(db: AsyncSession, org_id: uuid.UUID, sub, *, at_period_end: bool = True) -> None:
    try:
        if sub.stripe_subscription_id:
            await billing_stripe.cancel_stripe_subscription(db, org_id, at_period_end=at_period_end)
        else:
            from api.services import billing_paystack

            await billing_paystack.cancel_paystack_subscription(db, org_id, at_period_end=at_period_end)
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 -- the provider SDK/HTTP failure must not be hidden as a local cancellation
        logger.warning("billing: provider cancellation failed for organization %s: %s", org_id, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="The payment provider could not cancel the subscription; nothing was changed")


@org_router.post("/reactivate", response_model=SubscriptionResponse)
async def reactivate_subscription_endpoint(org_id: uuid.UUID, request: Request, caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    sub = await admin_subscriptions.get_or_create_subscription(db, org_id)
    if sub.stripe_subscription_id and sub.status == SubscriptionStatus.active and sub.canceled_at is not None:
        # Scheduled cancellation not yet effective: withdraw it at the provider too.
        try:
            await billing_stripe.resume_stripe_subscription(db, org_id)
        except ProviderNotConfiguredError as exc:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.warning("billing: provider reactivation failed for organization %s: %s", org_id, type(exc).__name__)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="The payment provider could not reactivate the subscription; nothing was changed")
    elif sub.stripe_subscription_id or sub.paystack_subscription_code:
        if sub.status == SubscriptionStatus.canceled:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This subscription has ended at the payment provider: start a new checkout instead")
    result = await admin_subscriptions.reactivate_subscription(db, sub.id)
    await _audit_billing(db, request, caller, org_id, AuditAction.BILLING_SUBSCRIPTION_REACTIVATED)
    await db.commit()
    return result


# -- 12.3 usage / credits -----------------------------------------------------

@org_router.get("/usage")
async def get_usage_endpoint(org_id: uuid.UUID, period_days: int = 30, _caller: OrganizationMember = Depends(require_permission("billing:read")), db: AsyncSession = Depends(get_db)):
    return await billing_usage.get_usage_breakdown(db, org_id, period_days)


@org_router.get("/usage/breakdown")
async def get_usage_breakdown_endpoint(org_id: uuid.UUID, period_days: int = 30, _caller: OrganizationMember = Depends(require_permission("billing:read")), db: AsyncSession = Depends(get_db)):
    return await billing_usage.get_usage_breakdown(db, org_id, period_days)


@org_router.get("/usage/forecast")
async def get_usage_forecast_endpoint(org_id: uuid.UUID, months: int = 1, _caller: OrganizationMember = Depends(require_permission("billing:read")), db: AsyncSession = Depends(get_db)):
    return await billing_usage.get_usage_forecast(db, org_id, months)


@org_router.get("/usage/alerts", response_model=list[UsageAlertResponse])
async def list_usage_alerts_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:read")), db: AsyncSession = Depends(get_db)):
    return await billing_usage.list_usage_alerts(db, org_id)


@org_router.post("/usage/alerts", response_model=UsageAlertResponse, status_code=status.HTTP_201_CREATED)
async def create_usage_alert_endpoint(org_id: uuid.UUID, body: CreateUsageAlertRequest, caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    alert = await billing_usage.create_usage_alert(db, org_id, resource_type=body.resource_type, threshold_percent=body.threshold_percent, user_id=caller.user_id)
    await db.commit()
    return alert


@org_router.delete("/usage/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_usage_alert_endpoint(org_id: uuid.UUID, alert_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    try:
        await billing_usage.delete_usage_alert(db, org_id, alert_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    await db.commit()


@org_router.get("/credits", response_model=CreditResponse)
async def get_credits_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:read")), db: AsyncSession = Depends(get_db)):
    credit = await billing_credits.get_or_create_credit(db, org_id)
    await db.commit()  # get_or_create_credit may INSERT a real Credit + its signup grant transaction
    return credit


@org_router.get("/credits/transactions", response_model=list[CreditTransactionResponse])
async def list_credit_transactions_endpoint(org_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0), _caller: OrganizationMember = Depends(require_permission("billing:read")), db: AsyncSession = Depends(get_db)):
    return await billing_credits.list_credit_transactions(db, org_id, limit, offset)


@org_router.get("/credits/packs")
async def list_credit_packs_endpoint(_caller: OrganizationMember = Depends(require_permission("billing:read"))):
    return CREDIT_PACKS


@org_router.post("/credits/purchase", response_model=CreditResponse)
async def purchase_credits_endpoint(org_id: uuid.UUID, body: PurchaseCreditsRequest, request: Request, caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    pack = get_credit_pack(body.pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown credit pack")
    # Hardening Mission (§23) -- this endpoint grants credits WITHOUT charging anything. The comment that used to
    # sit here said "without a configured Stripe account", but nothing ever checked that: with Stripe or Paystack
    # configured, any member holding `billing:manage` could mint unlimited free credits (a direct revenue bypass,
    # and a bypass of every credit-based cost control). It is now refused whenever the organization has a configured
    # payment provider (credits must come from a real checkout) and, with no provider, only while the deployment
    # allows unpaid top-ups (`CREDITS_ALLOW_UNPAID_TOPUP`, for self-hosted / dev instances).
    try:
        provider = await resolve_provider_for_organization(db, org_id)
    except ProviderNotConfiguredError:
        provider = None
    if provider is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Credits are purchased through the payment provider: start a checkout (POST .../billing/credits/checkout) instead of a direct top-up",
        )
    if not settings.CREDITS_ALLOW_UNPAID_TOPUP:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unpaid credit top-ups are disabled on this deployment")
    credit = await billing_credits.add_credits(db, org_id, pack["credits"], source=f"Purchased pack '{pack['name']}'", user_id=caller.user_id)
    await _audit_billing(db, request, caller, org_id, AuditAction.BILLING_CREDITS_ADDED, pack_id=body.pack_id, credits=pack["credits"], paid=False)
    await db.commit()
    return credit


@org_router.post("/credits/checkout", response_model=CheckoutSessionResponse)
async def credit_pack_checkout_endpoint(
    org_id: uuid.UUID, body: PurchaseCreditsRequest, caller: OrganizationMember = Depends(require_permission("billing:manage")),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Hardening Mission (§23) -- the REAL way to buy a credit pack when a payment provider is configured: returns a
    hosted checkout URL; the credits are granted by the provider's webhook once the payment is confirmed."""
    pack = get_credit_pack(body.pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown credit pack")
    try:
        provider = await resolve_provider_for_organization(db, org_id)
        url = await provider.create_credit_pack_checkout(db, org_id, pack=pack, email=current_user.email, org_name=str(org_id))
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    await db.commit()  # the checkout may INSERT a PaymentCustomer row
    return CheckoutSessionResponse(url=url)


# -- 12.4 invoices -------------------------------------------------------------

@org_router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices_endpoint(org_id: uuid.UUID, status_filter: InvoiceStatus | None = None, limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0), _caller: OrganizationMember = Depends(require_permission("billing:read")), db: AsyncSession = Depends(get_db)):
    return await billing_invoices.list_invoices(db, org_id, status_filter=status_filter, limit=limit, offset=offset)


@org_router.get("/invoices/stats", response_model=InvoiceStatsResponse)
async def invoice_stats_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    return await billing_invoices.get_invoice_stats(db, org_id)


@org_router.get("/invoices/{invoice_id}", response_model=InvoiceDetailResponse)
async def get_invoice_endpoint(org_id: uuid.UUID, invoice_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:read")), db: AsyncSession = Depends(get_db)):
    try:
        invoice = await billing_invoices.get_invoice(db, org_id, invoice_id)
    except billing_invoices.InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    lines = await billing_invoices.get_invoice_lines(db, invoice_id)
    return InvoiceDetailResponse(**InvoiceResponse.model_validate(invoice).model_dump(), lines=lines)


@org_router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf_endpoint(org_id: uuid.UUID, invoice_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:read")), db: AsyncSession = Depends(get_db)):
    from fastapi.responses import Response

    try:
        pdf_bytes = await billing_invoices.generate_invoice_pdf(db, org_id, invoice_id)
    except billing_invoices.InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    except billing_invoices.PDFUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return Response(content=pdf_bytes, media_type="application/pdf")


@org_router.post("/invoices/{invoice_id}/send", response_model=InvoiceResponse)
async def send_invoice_endpoint(org_id: uuid.UUID, invoice_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    try:
        invoice = await billing_invoices.send_invoice(db, org_id, invoice_id)
    except billing_invoices.InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    await db.commit()
    return invoice


@org_router.post("/invoices/{invoice_id}/remind", response_model=InvoiceResponse)
async def remind_invoice_endpoint(org_id: uuid.UUID, invoice_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    try:
        return await billing_invoices.remind_invoice(db, org_id, invoice_id)
    except billing_invoices.InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


@org_router.post("/invoices/{invoice_id}/pay", response_model=InvoiceResponse)
async def mark_invoice_paid_endpoint(org_id: uuid.UUID, invoice_id: uuid.UUID, request: Request, _caller: OrganizationMember = Depends(require_permission("billing:manage")), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # BILL-002 -- an organization must not be able to declare its own invoice paid: only the provider's webhook or the platform
    # superadmin (back-office reconciliation) may. Same opt-out as plans for self-hosted/dev instances.
    if current_user.role != UserRole.superadmin and not settings.BILLING_ALLOW_SELF_SERVICE_PAID_PLANS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invoices are marked paid by the payment provider once the payment is confirmed; organizations cannot mark them paid",
        )
    return await _settle_invoice_or_http_error(db, org_id, invoice_id, operation="paid", reason=None, actor=current_user, request=request)


async def _settle_invoice_or_http_error(db: AsyncSession, org_id: uuid.UUID, invoice_id: uuid.UUID, *, operation: str, reason: str | None, actor: User, request: Request, reference: str | None = None):
    try:
        invoice = await billing_invoices.settle_invoice(
            db, org_id, invoice_id, operation=operation, reason=reason, actor_id=actor.id, ip=client_ip(request), user_agent=request.headers.get("user-agent"), reference=reference,
        )
    except billing_invoices.InvoiceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    except billing_invoices.InvoiceStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await db.commit()
    return invoice


@org_router.post("/invoices/{invoice_id}/void", response_model=InvoiceResponse)
async def void_invoice_endpoint(org_id: uuid.UUID, invoice_id: uuid.UUID, body: VoidInvoiceRequest, request: Request, _caller: OrganizationMember = Depends(require_permission("billing:manage")), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # BILL-002 -- voiding cancels what the organization owes: a platform decision (superadmin), never the debtor's. A paid invoice
    # can never be voided (409). Same opt-out as `/pay` for self-hosted/dev instances without a payment provider.
    if current_user.role != UserRole.superadmin and not settings.BILLING_ALLOW_SELF_SERVICE_PAID_PLANS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invoices are voided by the platform; contact support to cancel an invoice")
    return await _settle_invoice_or_http_error(db, org_id, invoice_id, operation="void", reason=body.reason, actor=current_user, request=request)


# -- 12.2 Stripe (org-scoped checkout/portal/payment methods/invoices) --------

@org_router.post("/stripe/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session_endpoint(org_id: uuid.UUID, body: CheckoutSessionRequest, caller: OrganizationMember = Depends(require_permission("billing:manage")), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        url = await billing_stripe.create_checkout_session(db, org_id, price_id=body.price_id, email=current_user.email, org_name=str(org_id))
    except billing_stripe.StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    await db.commit()  # create_checkout_session may INSERT a real PaymentCustomer row
    return CheckoutSessionResponse(url=url)


@org_router.post("/stripe/create-portal-session", response_model=PortalSessionResponse)
async def create_portal_session_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    try:
        url = await billing_stripe.create_portal_session(db, org_id)
    except billing_stripe.StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    return PortalSessionResponse(url=url)


@org_router.get("/stripe/payment-methods", response_model=list[PaymentMethodResponse])
async def list_payment_methods_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    try:
        return await billing_stripe.list_payment_methods(db, org_id)
    except billing_stripe.StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))


async def _record_cancellation_request(db: AsyncSession, org_id: uuid.UUID) -> None:
    """The provider accepted a cancellation made through a provider-level route: record it locally the way `/cancel` does (canceled_at
    set, status unchanged). The status only moves to canceled when the provider's own event confirms it, so a cancellation that is
    still pending synchronization stays visible instead of being either invisible or reported as final."""
    sub = await admin_subscriptions.get_or_create_subscription(db, org_id)
    sub.canceled_at = sub.canceled_at or dt.datetime.now(dt.timezone.utc)


@org_router.delete("/stripe/payment-methods/{payment_method_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_payment_method_endpoint(
    org_id: uuid.UUID, payment_method_id: str, request: Request,
    caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db),
):
    try:
        await billing_stripe.detach_payment_method(
            db, org_id, payment_method_id
        )
    except billing_stripe.StripePaymentMethodNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment method not found") from exc
    except billing_stripe.StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    await _audit_billing(db, request, caller, org_id, AuditAction.BILLING_PAYMENT_METHOD_REMOVED)
    await db.commit()


@org_router.post("/stripe/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_stripe_subscription_endpoint(org_id: uuid.UUID, request: Request, at_period_end: bool = True, caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    try:
        await billing_stripe.cancel_stripe_subscription(db, org_id, at_period_end=at_period_end)
    except billing_stripe.StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    await _record_cancellation_request(db, org_id)
    await _audit_billing(db, request, caller, org_id, AuditAction.BILLING_SUBSCRIPTION_CANCELED, via="stripe", at_period_end=at_period_end)
    await db.commit()


@org_router.get("/stripe/invoices", response_model=list[StripeInvoiceResponse])
async def list_stripe_invoices_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
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


# -- Phase 5, Étape 2: Paystack webhook (flat, public, signature-verified) ----
# Same shape as the Stripe webhook above; Paystack calls a single fixed
# URL it can't parameterize with an org_id either, and its own event
# payload carries the organization via metadata/customer code (see
# api/services/billing_paystack.handle_paystack_webhook).

@router.post("/billing/paystack/webhook", status_code=status.HTTP_200_OK)
async def paystack_webhook_endpoint(request: Request, db: AsyncSession = Depends(get_db)):
    from api.services import billing_paystack

    payload = await request.body()
    signature = request.headers.get("x-paystack-signature", "")
    try:
        event = billing_paystack.verify_webhook_signature(payload, signature)
    except billing_paystack.PaystackNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Paystack signature")

    applied = await billing_paystack.handle_paystack_webhook(db, event)
    await db.commit()
    return {"received": True, "applied": applied}


# -- Phase 5, Étape 2: provider-generic checkout/portal/methods/cancel/invoices
# The pre-existing /stripe/... endpoints above are untouched (still real,
# still Stripe-only, kept for backward compatibility). These new
# endpoints are the actual "add PAYSTACK_SECRET_KEY to .env and it just
# works" surface: they resolve the org's own provider
# (api/services/billing_providers/registry.py, by organizations.billing_country)
# and dispatch to whichever one applies -- callers never need to know
# which provider an organization is on.

@org_router.get("/provider", response_model=BillingProviderResponse)
async def get_billing_provider_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:write")), db: AsyncSession = Depends(get_db)):
    try:
        provider = await resolve_provider_for_organization(db, org_id)
    except ProviderNotConfiguredError:
        return BillingProviderResponse(provider="none", configured=False)
    return BillingProviderResponse(provider=provider.name, configured=True)


@org_router.get("/country", response_model=BillingCountryResponse)
async def get_billing_country_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:write")), db: AsyncSession = Depends(get_db)):
    org = await db.get(Organization, org_id)
    return BillingCountryResponse(billing_country=org.billing_country if org else None)


@org_router.patch("/country", response_model=BillingCountryResponse)
async def update_billing_country_endpoint(org_id: uuid.UUID, body: BillingCountryUpdateRequest, request: Request, caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    org = await db.get(Organization, org_id)
    before = org.billing_country
    org.billing_country = body.billing_country
    await _audit_billing(db, request, caller, org_id, AuditAction.BILLING_COUNTRY_CHANGED, before=before, after=body.billing_country)
    await db.commit()
    return BillingCountryResponse(billing_country=org.billing_country)


@org_router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_unified_checkout_endpoint(org_id: uuid.UUID, body: UnifiedCheckoutRequest, caller: OrganizationMember = Depends(require_permission("billing:manage")), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        provider = await resolve_provider_for_organization(db, org_id)
        plan = await admin_subscriptions.get_plan(db, body.plan_id)
        url = await provider.create_checkout_session(db, org_id, plan=plan, billing_period=body.billing_period, email=current_user.email, org_name=str(org_id))
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    except PlanNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    await db.commit()
    return CheckoutSessionResponse(url=url)


@org_router.post("/portal", response_model=PortalSessionResponse)
async def create_unified_portal_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    try:
        provider = await resolve_provider_for_organization(db, org_id)
        url = await provider.create_portal_session(db, org_id)
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    return PortalSessionResponse(url=url)


@org_router.get("/payment-methods", response_model=list[PaymentMethodResponse])
async def list_unified_payment_methods_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    try:
        provider = await resolve_provider_for_organization(db, org_id)
        return await provider.list_payment_methods(db, org_id)
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))


@org_router.post("/cancel-active-subscription", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_unified_subscription_endpoint(org_id: uuid.UUID, request: Request, at_period_end: bool = True, caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    try:
        provider = await resolve_provider_for_organization(db, org_id)
        await provider.cancel_subscription(db, org_id, at_period_end=at_period_end)
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    await _record_cancellation_request(db, org_id)
    await _audit_billing(db, request, caller, org_id, AuditAction.BILLING_SUBSCRIPTION_CANCELED, via=provider.name, at_period_end=at_period_end)
    await db.commit()


@org_router.get("/provider-invoices", response_model=list[ProviderInvoiceResponse])
async def list_unified_provider_invoices_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("billing:manage")), db: AsyncSession = Depends(get_db)):
    try:
        provider = await resolve_provider_for_organization(db, org_id)
        return await provider.list_provider_invoices(db, org_id)
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
