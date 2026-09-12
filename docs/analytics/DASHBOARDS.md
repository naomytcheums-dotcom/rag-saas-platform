# Custom dashboards (Partie 20)

`AnalyticsDashboard` -- confirmed by audit to be the one genuinely
missing model in this whole part (every existing "dashboard" in this
codebase, the admin page and the quality dashboard, is hardcoded, not
a saved, per-organization, editable layout).

## Endpoints

- `GET/POST /organizations/{org_id}/analytics/dashboards` -- list/create.
- `GET/PATCH/DELETE .../dashboards/{id}` -- Member+ read, Admin+ write.

`widgets` is an opaque JSON list the backend stores and returns
verbatim -- the frontend (`DashboardBuilder.tsx`/`WidgetPicker.tsx`)
owns its shape (`{metric, chart, label}` today), the same
"opaque JSON, frontend-owned shape" convention as Partie 1.3.9's
`organization_settings`.

`is_default`: setting a dashboard as default automatically un-sets any
other dashboard that was previously default for the same organization
-- at most one real default at a time, enforced server-side, not left
to the frontend to coordinate.

## Frontend

`components/analytics/DashboardBuilder.tsx` -- create/list/set-default/
delete. `WidgetPicker.tsx` -- pick a metric + chart type
(line/bar/area/pie via `MetricChart.tsx`, backed by `recharts`, added
as this part's own first charting dependency -- confirmed by audit
that none existed before).
