# Selling as SaaS

Already real since Partie 12: plans (`docs/sales/PRICING.md`), Stripe
checkout/portal/webhooks (`docs/monitoring/GRAFANA_CLOUD_DATADOG_TWILIO.md`
covers observability, not billing — see `docs/billing/PARTIE_12_BILLING.md`
for Stripe), credits, invoices, a consolidated `/dashboard/billing` UI.

New in Partie 16 (bis): a real 14-day trial (`trial_ends_at`, starts
automatically at subscription creation) and real plan-limit enforcement
on document uploads (`402` when a plan's `max_documents` is reached).
Upgrade/downgrade is `POST /organizations/{org_id}/billing/upgrade`
(reuses the same `update_subscription` either direction — there's no
real distinction between "up" and "down" beyond which plan_id the
caller passes).
