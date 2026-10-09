# Billing

Full billing and monetization detail lives in
[`docs/billing/PARTIE_12_BILLING.md`](../billing/PARTIE_12_BILLING.md).
This page is the admin-facing quick reference.

## Viewing your plan and usage

**Admin → Billing** shows your current plan, billing period, and usage
against quota — see [Quotas & Limits](QUOTAS_AND_LIMITS.md).

## Changing plans

Upgrade, downgrade, or cancel from **Admin → Billing → Plan**. A paid plan
is activated only by a confirmed payment: the **Choose this plan** button
starts the provider checkout (`POST /organizations/{id}/billing/checkout`) and
the plan changes when the provider's verified webhook arrives. The direct
`subscribe` / `upgrade` / `downgrade` routes only accept a free plan or a
cheaper plan and answer `402` for anything else. Changes
typically take effect at the next billing cycle unless otherwise noted
at checkout.

## Invoices

Past invoices are available under **Admin → Billing → Invoices**. An
organization cannot mark its own invoice as paid (`403`); only the payment
provider's webhook or a platform admin can.

## Self-hosted deployments

If you're self-hosted, billing may not apply at all, or may be handled
outside the platform depending on your agreement — see
[Self-hosted install](../install/SELF_HOSTED.md) and
[`docs/sales/SELF_HOSTED.md`](../sales/SELF_HOSTED.md).

Direct credit top-ups without a payment provider are disabled by default.
For a private self-hosted or development deployment only, explicitly set
`CREDITS_ALLOW_UNPAID_TOPUP=true`; public deployments should keep it disabled
and use the provider checkout and verified webhook flow.

Likewise, `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS` (default `false`) lets an
organization owner move to a paid plan through `subscribe` / `upgrade` and
mark invoices paid by hand, with no payment. Enable it only on a private
self-hosted or development deployment that has no payment provider; never on
a public deployment.
