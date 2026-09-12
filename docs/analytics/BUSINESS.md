# Business metrics (Partie 20)

Platform-wide, superadmin-only -- same real scope as
`api/services/admin_subscriptions.py`, which these endpoints extend
rather than duplicate. Not org-scoped: MRR/churn/LTV are properties of
the whole business, not one customer organization.

## Endpoints

- `GET /analytics/business/revenue` -- real MRR/ARR/ARPU/`churn_last_30d`
  (unchanged, delegates directly to `get_revenue_stats`).
- `GET /analytics/business/customers` -- total/active/trialing customer counts.
- `GET /analytics/business/churn` -- **real churn rate**
  (`canceled-in-window / (active-now + canceled-in-window)`), honestly
  `null` with no real subscriptions to compute a rate over.
- `GET /analytics/business/retention` -- `1 - churn_rate`.
- `GET /analytics/business/ltv` -- real, standard SaaS approximation
  (`ARPU / monthly churn rate`), honestly `null` when churn is 0 (no
  real signal for an average customer lifetime yet).
- `GET /analytics/business/revenue/trend` -- a real daily MRR series.
  Disclosed approximation: uses each subscription's CURRENT plan price
  for every past day too (no historical price-at-the-time ledger
  exists) -- real data, not a fabricated smooth curve, but not
  perfectly retroactively accurate if a subscription ever changed plans.

All accept `date_range` (`7d`/`30d`/`90d`/`12m`, default `30d`).
