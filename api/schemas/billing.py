"""Request/response bodies for Partie 12 (billing: plans, Stripe, credits/usage, invoices)
and Phase 5, Étape 2 (Paystack + provider-generic checkout/portal)."""

import datetime as dt
import uuid

from pydantic import BaseModel, field_validator

from api.models.admin import SubscriptionStatus
from api.models.billing import CreditTransactionType, InvoiceStatus


# -- 12.1 plans -------------------------------------------------------------

class PlanResponse(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    monthly_price_cents: int
    yearly_price_cents: int
    max_documents: int | None
    max_agents: int | None
    max_members: int | None
    max_api_keys: int | None
    max_webhooks: int | None
    max_requests_per_month: int | None
    monthly_credits_included: int | None
    priority_support: bool
    advanced_features: bool
    sla: bool
    is_active: bool
    stripe_price_id_monthly: str | None = None
    stripe_price_id_yearly: str | None = None
    paystack_plan_code_monthly: str | None = None
    paystack_plan_code_yearly: str | None = None

    model_config = {"from_attributes": True}


class PlanCreateRequest(BaseModel):
    key: str
    name: str
    monthly_price_cents: int
    yearly_price_cents: int = 0
    max_documents: int | None = None
    max_agents: int | None = None
    max_members: int | None = None
    max_api_keys: int | None = None
    max_webhooks: int | None = None
    max_requests_per_month: int | None = None
    priority_support: bool = False
    advanced_features: bool = False
    sla: bool = False
    paystack_plan_code_monthly: str | None = None
    paystack_plan_code_yearly: str | None = None


class PlanUpdateRequest(BaseModel):
    name: str | None = None
    monthly_price_cents: int | None = None
    yearly_price_cents: int | None = None
    max_documents: int | None = None
    max_agents: int | None = None
    max_members: int | None = None
    max_api_keys: int | None = None
    max_webhooks: int | None = None
    max_requests_per_month: int | None = None
    priority_support: bool | None = None
    advanced_features: bool | None = None
    sla: bool | None = None
    is_active: bool | None = None
    paystack_plan_code_monthly: str | None = None
    paystack_plan_code_yearly: str | None = None


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    plan_id: uuid.UUID
    status: SubscriptionStatus
    billing_period: str
    current_period_end: dt.datetime | None
    canceled_at: dt.datetime | None

    model_config = {"from_attributes": True}


class SubscribeRequest(BaseModel):
    plan_id: uuid.UUID
    billing_period: str = "monthly"


class CancelSubscriptionRequest(BaseModel):
    reason: str | None = None


# -- 12.2 Stripe --------------------------------------------------------------

class CheckoutSessionRequest(BaseModel):
    price_id: str


class CheckoutSessionResponse(BaseModel):
    url: str


class PortalSessionResponse(BaseModel):
    url: str


class PaymentMethodResponse(BaseModel):
    id: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int


class StripeInvoiceResponse(BaseModel):
    id: str
    number: str | None
    status: str
    total: int
    currency: str
    hosted_invoice_url: str | None


# -- Phase 5, Étape 2: provider-generic checkout/portal (Stripe or Paystack) --

class UnifiedCheckoutRequest(BaseModel):
    """Body of the new, provider-generic POST .../billing/checkout --
    unlike the Stripe-only CheckoutSessionRequest above (which takes a
    raw `price_id`), this takes the org's own `plan_id` and lets the
    resolved provider (api/services/billing_providers/registry.py) look
    up its own price/plan-code from that Plan row -- a raw Stripe price
    id has no Paystack equivalent to accept instead."""

    plan_id: uuid.UUID
    billing_period: str = "monthly"


class ProviderInvoiceResponse(BaseModel):
    id: str
    number: str | None
    status: str
    total: int
    currency: str
    hosted_invoice_url: str | None


class BillingProviderResponse(BaseModel):
    provider: str
    configured: bool


class BillingCountryUpdateRequest(BaseModel):
    billing_country: str | None = None

    @field_validator("billing_country")
    @classmethod
    def _validate_iso_alpha2(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if len(value) != 2 or not value.isalpha():
            raise ValueError("billing_country must be a 2-letter ISO 3166-1 alpha-2 code, e.g. 'NG' or 'FR'")
        return value


class BillingCountryResponse(BaseModel):
    billing_country: str | None


# -- 12.3 credits / usage ------------------------------------------------------

class CreditResponse(BaseModel):
    organization_id: uuid.UUID
    balance: int

    model_config = {"from_attributes": True}


class CreditTransactionResponse(BaseModel):
    id: uuid.UUID
    type: CreditTransactionType
    amount: int
    balance_after: int
    reason: str | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class PurchaseCreditsRequest(BaseModel):
    pack_id: str


class UsageAlertResponse(BaseModel):
    id: uuid.UUID
    resource_type: str
    threshold_percent: int

    model_config = {"from_attributes": True}


class CreateUsageAlertRequest(BaseModel):
    resource_type: str
    threshold_percent: int


# -- 12.4 invoices --------------------------------------------------------------

class InvoiceLineResponse(BaseModel):
    id: uuid.UUID
    description: str
    quantity: int
    unit_price_cents: int
    total_cents: int

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    number: str
    status: InvoiceStatus
    currency: str
    subtotal_cents: int
    vat_cents: int
    total_cents: int
    due_date: dt.date | None
    paid_at: dt.datetime | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class InvoiceDetailResponse(InvoiceResponse):
    lines: list[InvoiceLineResponse]


class VoidInvoiceRequest(BaseModel):
    reason: str | None = None


class InvoiceStatsResponse(BaseModel):
    total_paid_cents: int
    total_outstanding_cents: int
    overdue_count: int
