# Partner program (Partie 18)

Real, honest scope: this extends Partie 16 (bis)'s reseller/sub-client
infrastructure (`api/models/sales.py`) rather than duplicating it under
new names -- a `Partner` in the spec IS a `Reseller` row here, and a
`PartnerClient` IS a `SubClient` row. The one genuine gap Partie 16
(bis) left open -- a persisted, payable commission ledger -- is what
Partie 18 actually adds.

## What already existed (Partie 16 bis, not duplicated)

- `Reseller`/`SubClient` models, `POST /reseller/create` (superadmin),
  `POST /reseller/{id}/clients` (superadmin), `GET /reseller/{id}/clients`,
  `GET /reseller/{id}/commission` (live MRR calculation, not persisted).

## What Partie 18 adds

- **Self-service signup**: `POST /partners/register` (public) --
  creates a real user account, organization, and `Reseller` row in one
  call, at `settings.PARTNER_DEFAULT_COMMISSION` (default 20%). No
  superadmin action needed for a prospective partner to get started.
- **Partner-facing "me" endpoints** (any authenticated user who is a
  member of a reseller's organization): `GET /partners/me`,
  `GET /partners/me/clients`, `GET /partners/me/commissions`.
- **The real commission ledger** -- `PartnerCommission`
  (`api/models/sales.py`, migration `0099_partner_commissions.py`):
  one persisted row per reseller per billing period, `pending` or
  `paid`, with a real `paid_at` timestamp. `calculate_reseller_commission`
  (Partie 16 bis) is still the live, on-demand calculation; this is
  the append-only history a partner and this platform can actually
  audit later.
  - `GET /partners/{reseller_id}/commissions` (superadmin)
  - `POST /partners/commissions/{commission_id}/pay` (superadmin, manual, one at a time)
- **Automated commission runs** (`api/tasks/sales.py`, Celery Beat):
  - `calculate_partner_commissions` -- monthly, for the month just
    elapsed. Idempotent: re-running it for a period that already has a
    row does nothing.
  - `pay_partner_commissions` -- daily. Sums each reseller's pending
    commissions and marks them paid **only once the total reaches
    `settings.PARTNER_MIN_PAYOUT_CENTS`** (default 100 EUR) -- a
    partner owed less stays honestly pending. **No real money moves**:
    no Stripe Connect transfer (or any other payout rail) is wired up
    here -- this flips the real ledger state a finance process still
    has to act on, same scope as this app's other "mock unless a real
    provider is configured" services.

## Config

- `PARTNER_PROGRAM_ENABLED` (default `true`) -- a deployment-mode
  declaration, not a feature gate: every endpoint above works
  regardless of this flag today.
- `PARTNER_DEFAULT_COMMISSION` (default `20`, percent)
- `PARTNER_MIN_PAYOUT_CENTS` (default `10000` = 100 EUR)

## Honest gaps not built in this pass

- No real payout rail (Stripe Connect or otherwise) -- `pay_partner_commissions`
  only updates the ledger's own status.
- No partner-branded referral link / attribution tracking -- a
  superadmin still manually assigns a `SubClient` to a `Reseller` via
  `POST /reseller/{id}/clients` (a self-service "sign up via my
  referral link" flow is not built).
- Frontend: `frontend/components/partners/PartnerDashboard.tsx` and
  `CommissionList.tsx` cover the partner's own view (composed in
  `/dashboard/partners`); there is no admin-facing partner-management
  UI (superadmin actions above are API-only, same as Partie 16 (bis)'s
  reseller endpoints already were).
