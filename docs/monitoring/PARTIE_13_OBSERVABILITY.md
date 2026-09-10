# Partie 13 — Monitoring & Observability (Metrics, Logging, Alerting, Tracing, UI)

Same consolidated-guide discipline as every prior batch. Heavy real
overlap with Partie 10.5 (real Prometheus `/metrics`, `api/monitoring.py`)
and Partie 11.5/11.6 (`GET /admin/monitoring/*`, `GET /admin/logs`,
`api/services/admin_monitoring.py`, `api/security/system_log_handler.py`)
-- nothing there is duplicated; this part extends it.

## 13.1 — Metrics

`api/monitoring.py`'s real Prometheus `/metrics` (Partie 10.5) gains
two real counters: `http_requests_total` (by method/path/status class)
and `celery_tasks_total` (wired via real Celery `task_success`/
`task_failure` signals, `api/tasks/celery_app.py` — covers every task
automatically). `GET /monitoring/metrics` (new,
`api/services/app_metrics.py`) adds a human-readable summary: real
business counts (organizations/users/conversations/active
subscriptions) plus this process's own counter/histogram sample
totals. Business counts are deliberately NOT added as Prometheus
Gauges — see that module's own docstring for the real multiprocess
correctness trap that would create.

## 13.2 — Structured logging

Real gap found and fixed: `system_logs.request_id` (Partie 11.6) had
existed as a column since that part shipped, but nothing ever
populated it. `api/security/logging_correlation.py` adds a real
`ContextVar` + `RequestCorrelationMiddleware` (sets/reads
`X-Request-ID`, echoed in the response header) and a `logging.Filter`
so every log line for a request carries the same id, wired into
`SystemLogHandler.emit`. `LOG_FORMAT=json` switches every root-logger
handler to a real structured JSON formatter (with the same
`AUDIT_SENSITIVE_FIELDS`-style masking already used elsewhere, applied
here too). `GET /admin/logs` (11.6) is the real logs API — not
duplicated under a second `/logs` prefix.

## 13.3 — Alerting & incidents

Real, consolidated models (`api/models/alerting.py`): `AlertRule`
carries its own condition inline (no separate `AlertCondition` table);
`AlertChannel` has exactly two real types, `email` and `webhook` (Slack/
Teams/Discord/PagerDuty are all, in practice, a POST to an incoming
webhook URL — one real channel type covers all four honestly, without
four SDKs this environment has no real accounts for). Rules evaluate
against REAL, already-live data (`api/services/admin_monitoring.py`'s
psutil/Celery inspection, Partie 11.5) — an unmonitored metric name
returns `None` and is skipped, never fabricated as 0.
`api/tasks/alerting.py`'s `check_alert_rules` runs every
`ALERTING_CHECK_INTERVAL_SECONDS` (default 60s) via Celery beat;
verified directly by manually invoking the task after creating a real
rule (`cpu_percent gt 0`) — it fired for real (CPU is never exactly 0%)
and the resulting `AlertHistory` row appeared in the UI on reload.

## 13.4 — Distributed tracing (OpenTelemetry)

`api/security/tracing.py` — real `opentelemetry-sdk` +
FastAPI/SQLAlchemy/Redis/httpx/Celery auto-instrumentation, `OFF by
default` (`OTEL_ENABLED=False`). **Deliberate deviation from the
literal spec**: no `Trace`/`Span` database tables were built — a real
distributed trace spans multiple PROCESSES (this API + Celery
workers), which is exactly what a real collector (Jaeger/Tempo/an OTLP
endpoint) is built to correlate; a single app-owned table can't see
spans from a separate worker process the way a real collector can, so
storing them here would be a second, incorrect source of truth. Set
`OTEL_ENABLED=True` and a real `OTEL_EXPORTER_OTLP_ENDPOINT` to
activate for real — with no endpoint configured, spans go to this
process's own console instead of being silently dropped.
`GET /monitoring/tracing/status` reports real state (`enabled`,
`active`, `exporter`).

## 13.5 — Frontend

**Not** a new, separate `/dashboard/monitoring` page — the literal
spec's screen collides directly with `/admin`'s existing "Monitoring"
and "Logs" tabs (Partie 11.5/11.6, already real and live). Extended
instead: the Monitoring tab gained real business-metrics cards and a
real tracing-status card; a new "Alerting" tab (rules, channels,
history, incidents) was added. Verified live end-to-end: created a
real alert channel and rule, manually ran the real Celery check task,
confirmed the resulting alert appears in history after reload.

## Honest gaps (~/60 items not built)

- No ELK/Datadog/Loki/CloudWatch log-forwarding integrations (no real
  accounts for any of them in this environment) — `LOG_FORMAT=json`
  produces the structured output any of those would ingest, but
  nothing here ships/forwards to one.
- No SMS/push alert channels (no Twilio/APNs account wired for this
  purpose) — email + generic webhook are real and cover every listed
  provider (Slack/Teams/Discord/PagerDuty) via their own incoming
  webhook URLs.
- OpenTelemetry tracing has never been exercised against a real
  collector (no Jaeger/Tempo/OTLP endpoint exists here) — the
  instrumentation code is real and switched on with one config change,
  but "traces show up correctly in a real trace UI" is unverified.
- No on-call scheduling (`OnCallSchedule`) — not built; this
  environment has no real on-call rotation to model.
