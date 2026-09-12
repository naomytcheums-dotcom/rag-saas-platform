# Advanced analytics (Partie 20)

Real, honest scope note first: an audit of the existing codebase
(this part's own instructions, item 1) found that Prometheus metrics
(`api/monitoring.py`), system health/resources (`api/services/admin_monitoring.py`),
revenue/MRR/ARR/ARPU/churn-count (`api/services/admin_subscriptions.py`),
a per-org daily usage ledger (`api/models/organization_usage.py`), a
RAG-response quality dashboard (`api/services/quality_dashboard.py`),
and per-evaluation token/cost tracking (`api/services/token_usage.py`/
`cost_tracking.py`) were ALL already real. None of that was duplicated.
Genuinely new: `AnalyticsEvent` (a free-form product-telemetry log,
distinct from `AuditLog`'s closed, security-relevant action enum),
`AnalyticsAggregate` (materialized per-period rollups), and
`AnalyticsDashboard` (a saved, user-configurable widget layout).

## Generic events and metrics

`POST /organizations/{org_id}/analytics/events` records a real,
free-form `event_type` (e.g. `"document.uploaded"`) with arbitrary
`event_data`. `GET .../analytics/metrics` reads the pre-aggregated
rollup table (fast); `GET .../analytics/metrics/query` reads raw
events directly (for ad-hoc exploration the rollups don't cover);
`GET .../analytics/metrics/export?format=csv|json` exports either,
bounded by `ANALYTICS_MAX_EXPORT_ROWS`.

## Config

- `ANALYTICS_ENABLED` (default `true`)
- `ANALYTICS_RETENTION_DAYS` (default `365`) -- governs `AnalyticsEvent`
  only; `AnalyticsAggregate` rollups and `AuditLog` have their own,
  separate retention.
- `ANALYTICS_AGGREGATION_ENABLED` (default `true`)
- `ANALYTICS_MAX_EXPORT_ROWS` (default `100000`)
- `ANALYTICS_DEFAULT_PERIOD` (default `"30d"`)

## Celery jobs

`aggregate_metrics_hourly`/`_daily`/`_monthly` -- real, idempotent
rollups (re-running for an already-computed period overwrites, never
duplicates -- see the unique index on `AnalyticsAggregate`).
`cleanup_old_events` -- deletes `AnalyticsEvent` rows past
`ANALYTICS_RETENTION_DAYS`. `send_analytics_report` -- emails an org
owner a real, current 30-day event count.

See `docs/analytics/BUSINESS.md`, `PRODUCT.md`, `TECHNICAL.md`,
`DASHBOARDS.md` for each metric area's own real scope.
