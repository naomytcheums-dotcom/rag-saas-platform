# White-label configuration (Partie 19)

Real, honest scope note first: the spec for this part asked for a new
`WhiteLabelConfig` model with 15 fields. An audit of the existing
codebase (done before writing any code, per this part's own
instructions) found that 9 of those 15 fields already existed on
`OrganizationBranding` (Partie 1.3.10) and 2 more (`domain`/
`domain_verified`) already existed on `CustomDomain` (Partie 1.4.1).
Building a second table would have created two independent,
potentially-disagreeing sources of truth for the same data -- the
exact mistake `api/security/white_label.py`'s own docstring already
documented rejecting once, for the same reason. So: `organization_branding`
was extended with the 6 genuinely new columns
(`company_email`/`support_email`/`email_sender_name`/`email_sender_email`/
`custom_js`/`is_active`, migration `0101`), and the full config is a
computed view over `organization_branding` + `custom_domains` -- one
real row, not a duplicate.

## Endpoints

All under `/organizations/{org_id}/whitelabel/...` (Member+ for reads,
Admin+ for writes -- one tier laxer than the pre-existing
`/organizations/{org_id}/white-label` toggle endpoint, which stays
Owner-only and untouched):

- `GET /whitelabel/config` -- the full config
- `PATCH /whitelabel/config` -- colors, brand name, contact emails,
  custom CSS/JS, the `hide_platform_branding` toggle, and `is_active`
- `POST /whitelabel/domain` / `DELETE /whitelabel/domain` / `POST
  /whitelabel/domain/verify` -- see `docs/whitelabel/DOMAIN.md`
- `POST /whitelabel/email` / `DELETE /whitelabel/email` -- see
  `docs/whitelabel/EMAIL.md`
- `POST /whitelabel/logo` / `DELETE /whitelabel/logo` / `POST
  /whitelabel/favicon` -- delegate to the exact same real S3
  upload/validation `api/services/storage.py` already provides for
  Partie 1.3.10's own branding endpoints, not reimplemented
- `GET /whitelabel/preview` -- the same config, with `is_active`'s own
  kill switch applied (an inactive config previews as pure platform
  defaults, real domain/domain_verified excepted -- those are facts
  about the organization regardless of the visual toggle)
- `POST /whitelabel/reset` -- restores brand colors/name/custom
  CSS-JS/contact emails/hide-flag to platform defaults. Deliberately
  does NOT touch an uploaded logo/favicon (clearing the pointer without
  deleting the real file would just orphan it) or the custom domain --
  those are separate, explicit decisions with their own endpoints.

## is_active vs hide_platform_branding

Two different real switches, easy to confuse:

- `hide_platform_branding` (Partie 1.4.6) hides only THIS platform's
  own name/logo/legal mentions in favor of the organization's.
- `is_active` (Partie 19) is a full kill switch: when `false`, every
  custom field (colors, name, CSS/JS, contact emails) is ignored and
  the real platform defaults render instead -- the saved configuration
  itself is untouched and comes back the moment it's flipped back on.

## Real domain-detection middleware

`api/services/white_label_middleware.py` resolves the request's `Host`
header against `custom_domains` on every request, attaching
`request.state.white_label_organization_id`/`white_label_config` for
any downstream code that wants to key off the visiting domain (e.g. a
future public, domain-driven page). It does not rewrite routing or
inject branding into responses itself -- see that module's own
docstring, including a real bug caught and fixed while testing it (an
earlier version bypassed the test suite's database override and
silently hit this deployment's real production database on every
single request).

## Custom JS: a real, accepted risk, not a false promise of safety

`custom_css` is checked against a real list of historically-exploitable
CSS constructs (`api/security/organization_branding.py`'s
`validate_custom_css`). `custom_js` is NOT sanitized the same way --
there is no meaningful pattern-based sanitization for arbitrary
JavaScript. The real security boundary is who can set it
(`require_org_admin`, same as everything else here) and where it runs
(only that organization's own white-labeled page) -- the same trust
model as embedding any third-party widget script. Only a length limit
(20,000 characters) is enforced.
