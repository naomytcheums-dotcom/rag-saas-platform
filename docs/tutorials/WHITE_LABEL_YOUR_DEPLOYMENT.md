# Tutorial: White-label Your Deployment

See [White-label](../admin/WHITE_LABEL.md) for the full reference.

## 1. Hide platform branding

**Admin → Branding → hide_platform_branding**. Requires a plan that
includes white-labeling.

## 2. Add a custom domain

**Admin → Domains → Add domain**. Enter your domain, then follow the
DNS instructions shown — see
[`docs/whitelabel/DOMAIN.md`](../whitelabel/DOMAIN.md).

## 3. Complete SSL verification

SSL uses DNS-01 verification against Let's Encrypt — you'll be asked to
create a specific DNS TXT record manually (this step is not automated,
see [SSL & Domains](../install/SSL_AND_DOMAINS.md)). Once the record
propagates, trigger verification in the dashboard.

## 4. Custom email domain (optional)

To send platform emails from your own domain instead of the platform's
default, see [`docs/whitelabel/EMAIL.md`](../whitelabel/EMAIL.md).

## 5. Reseller branding (optional)

If you're a partner reselling under your own brand entirely, see
[`docs/whitelabel/RESELLER.md`](../whitelabel/RESELLER.md) and
[`docs/partners/ONBOARDING.md`](../partners/ONBOARDING.md).
