# White-label

Full white-labeling detail is in
[`docs/whitelabel/CONFIGURATION.md`](../whitelabel/CONFIGURATION.md),
[`docs/whitelabel/DOMAIN.md`](../whitelabel/DOMAIN.md),
[`docs/whitelabel/EMAIL.md`](../whitelabel/EMAIL.md), and
[`docs/whitelabel/RESELLER.md`](../whitelabel/RESELLER.md). This page
is the admin quick-start.

## Hiding platform branding

**Admin → Branding → hide_platform_branding**. Available on plans that
include white-labeling.

## Custom domain

Point your own domain at your deployment — see
[`docs/whitelabel/DOMAIN.md`](../whitelabel/DOMAIN.md) for DNS setup and
[SSL & Domains](../install/SSL_AND_DOMAINS.md) for the certificate
side. SSL automation is DNS-01 based and verified against Let's Encrypt
staging — not "fully automatic" without a DNS-provider API integration,
a real documented limitation.

## Custom email domain

Send platform emails (invitations, notifications) from your own domain
instead of the platform's default — see
[`docs/whitelabel/EMAIL.md`](../whitelabel/EMAIL.md).

## Reseller / partner branding

If you're a partner reselling the platform under your own brand, see
[`docs/whitelabel/RESELLER.md`](../whitelabel/RESELLER.md) and
[`docs/partners/ONBOARDING.md`](../partners/ONBOARDING.md).
