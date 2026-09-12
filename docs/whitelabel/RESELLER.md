# White-label for resellers

A reseller/agency (Partie 18's own `Reseller`/`SubClient`/partner
program, `docs/sales/PARTNER_PROGRAM.md`) sells this platform under
their own brand to their sub-clients. White-label (Partie 19) is what
makes that brand real and visible:

1. **Set your brand** -- `PATCH /organizations/{org_id}/whitelabel/config`
   (colors, company name, hide this platform's own branding) plus a
   real uploaded logo/favicon (`POST .../whitelabel/logo`, `.../favicon`).
2. **Point your own domain at it** -- `docs/whitelabel/DOMAIN.md`.
3. **Set your own support contact identity** -- `docs/whitelabel/EMAIL.md`
   and the `company_email`/`support_email` fields on the config.
4. **Preview before you go live** -- `GET .../whitelabel/preview`
   (or `PreviewBranding.tsx` on `/dashboard/whitelabel`) shows exactly
   what a visitor sees, including the real effect of the `is_active`
   kill switch if you need to temporarily fall back to platform
   defaults without losing your saved configuration.

## Which organization's white-label applies to your sub-clients

**Important, honest scope**: white-label configuration is per
ORGANIZATION, not per reseller relationship. Setting your own
`organization_id`'s white-label config brands YOUR OWN organization's
pages. It does not automatically re-brand every sub-client
organization Partie 18's `SubClient` table lists under you -- each
sub-client is its own real, independent tenant with its own real
users/documents/billing (see `api/models/sales.py`'s own docstring on
`SubClient`), and, today, its own independent white-label
configuration if it wants one. A reseller-wide "apply my branding to
all my sub-clients automatically" feature is not built in this pass --
a real, disclosed gap, not something quietly assumed to already work.
