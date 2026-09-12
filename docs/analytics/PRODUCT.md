# Product metrics (Partie 20)

Per-organization, Member+. Built on the new `AnalyticsEvent` table
(product telemetry) and the existing `OrganizationUsage` ledger --
starts honestly empty until real events are actually tracked via
`POST /organizations/{org_id}/analytics/events`.

## Endpoints

- `GET .../product/usage` -- real per-metric totals from
  `OrganizationUsage` (the same ledger `api/services/billing_usage.py`
  already reads) over the window.
- `GET .../product/adoption` -- for each real `event_type` this org has
  generated, its total event count and distinct-user count.
- `GET .../product/engagement` -- a real daily-active-users series
  (distinct users who generated at least one event, per day).
- `GET .../product/funnels?steps=a,b,c` -- for an ordered, comma-separated
  list of `event_type` names, the count of distinct users who reached
  each step. A step nobody has ever triggered honestly reports `0`, not
  a fabricated conversion percentage.

## Wiring your own events

Call `POST .../analytics/events` with `{"event_type": "...", "event_data": {...}}`
from any real product action -- e.g. conversation creation, document
upload, agent creation. `event_type` is a free-form string (unlike
`AuditLog`'s closed action enum) so a new feature never needs a
migration just to start tracking its own adoption.
