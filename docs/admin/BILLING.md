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
organization cannot mark its own invoice as paid or void (`403`).

### Invoice states and who can change them

| From | To `paid` | To `void` |
|---|---|---|
| `draft` (never issued) | **refused** (`409`) | allowed |
| `pending`, `sent`, `overdue` | allowed | allowed |
| `paid` | no-op (first payment date kept) | **refused** (`409`) |
| `void` | **refused** (`409`) | no-op |
| `refunded` | refused | refused |

- Payments confirmed by Stripe or Paystack are applied by their own verified
  webhook chain (signature + event idempotence); no manual reference is needed.
- Marking an invoice paid **by hand** is a platform **superadmin** act, through
  `POST /admin/organizations/{org}/invoices/{invoice}/mark-paid` (or the
  organization route `.../billing/invoices/{invoice}/pay` for a superadmin who
  is a member). A payment `reference` (bank transfer id, receipt number, at
  least 3 characters) is mandatory (`422` otherwise, invoice unchanged) and is
  kept in the audit row. No partial payments.
- Voiding is a superadmin act and needs a non-blank `reason` (`422`
  otherwise); both are audited with the previous and the new state.
- On a self-hosted instance with `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS=true`
  an organization owner may do both itself; the reference is optional there and
  the audit row carries `self_service: true`.
- **`refunded` is not managed**: the state exists in the data model but no
  route sets it and refunds are not implemented (`POST /admin/subscriptions/{id}/refund`
  answers `501` until a payment processor flow is built).
- **Paying or voiding an invoice does not change the subscription status.**
  A `past_due` subscription becomes `active` again through the payment
  provider's events or an explicit superadmin action, never as a side effect
  of an invoice change; credits are not touched either.

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
