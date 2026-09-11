# Selling as white-label

## Already real, not rebuilt

- **Full customization** (logo, colors, font, brand name, custom CSS,
  `hide_platform_branding`) — `OrganizationBranding`, Partie 1.3.10.
- **Custom domain** (CNAME, e.g. `app.client-brand.com`) — `CustomDomain`,
  Partie 1.4.1, with real SSL via Let's Encrypt, Partie 1.4.3.
- **Custom emails** (a client's own verified domain sends their own
  transactional emails, not `@this-platform.com`) — `send_via_custom_email_domain`,
  reusing the same `CustomDomain` row, Partie 1.4.5.

## New in Partie 16 (bis): reseller API + sub-clients

`Reseller` (one real platform partner, tied to their own real
organization — which itself gets the real branding/domain/email
features above) and `SubClient` (one real, ordinary tenant
Organization the reseller manages, tagged with which reseller brought
it on).

- `POST /reseller/create` (superadmin)
- `POST /reseller/{id}/clients` — add a real organization as a sub-client
- `GET /reseller/{id}/clients` — list them
- `GET /reseller/{id}/commission` — real commission math: sums the real
  MRR of every real, active, paid Subscription across the reseller's
  real sub-clients, applies `commission_percent` — the same honest "0
  until a real paying organization exists" math as `admin_subscriptions.py`'s
  own `get_revenue_stats`, never a fabricated number.

A sub-client is a real, first-class Organization — it can use every
feature any other organization can, including its OWN white-label
branding/domain if the reseller's contract allows it.
