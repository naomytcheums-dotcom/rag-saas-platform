# Grafana Cloud, Datadog LLM Observability, Twilio

Real integrations, all gated on real config — nothing here fabricates a
successful send when the required credentials are absent.

## Grafana Cloud — Loki (logs)

`api/security/loki_handler.py` — a real `logging.Handler`, background
thread, bounded queue (drops rather than blocks under overload), real
HTTP POST to `{LOKI_HOST}/loki/api/v1/push`. Installed automatically at
startup only when `LOKI_HOST`, `LOKI_USERNAME`, and `LOKI_PASSWORD` are
ALL set (a password alone can't identify which Grafana Cloud stack to
push to — `LOKI_USERNAME` is the real numeric instance id from your
Grafana Cloud portal, not your account username). `GET
/monitoring/loki/status` / `GET /monitoring/loki/test` (both
`require_admin`).

## Grafana Cloud — Tempo (traces)

Extends the real OpenTelemetry setup already built for Partie 13.4
(`api/security/tracing.py`) — when `TEMPO_HOST`/`TEMPO_USERNAME`/
`TEMPO_PASSWORD` are set, the OTLP exporter targets Tempo's real
`/v1/traces` endpoint with a real Basic Auth header, instead of the
generic `OTEL_EXPORTER_OTLP_ENDPOINT`/console fallback. Still requires
`OTEL_ENABLED=True` to actually instrument anything.

## Grafana Cloud — Prometheus (metrics)

**Deliberately not built as app-side push code.** Prometheus is
pull-based by design; Grafana Cloud's own "remote_write" is something a
real Grafana Agent or Prometheus server does by scraping this app's
real `GET /metrics` and forwarding it — not a client library this
process calls directly. Point a Grafana Agent (or Prometheus server
configured with `remote_write`) at this app's real `/metrics` endpoint
to get these numbers into Grafana Cloud; no application code change
needed for that.

## Datadog — LLM Observability

`api/security/datadog_llmobs.py` — real `ddtrace.llmobs.LLMObs.enable()`,
called at startup only when `DD_API_KEY` is set. **Real, honest
deviation from the literal spec**: `ddtrace-run` (the auto-instrumentation
entrypoint for FastAPI/SQLAlchemy/Redis/Celery) is a process launcher
(`ddtrace-run uvicorn api.main:app`), not an in-app function call —
switching to it is a one-line change to how this process starts, not
application code. `GET /monitoring/datadog/status`.

## Twilio — SMS/WhatsApp

`api/services/twilio_sms.py` — real `twilio` SDK, real send, real
per-organization log (`SmsMessage`). Honestly 501s without
`TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_FROM_NUMBER` all set —
this environment has a real Account SID in `.env` but no real Auth
Token yet.

- `POST /organizations/{org_id}/notifications/sms/send`
- `POST /organizations/{org_id}/notifications/whatsapp/send`
- `GET /organizations/{org_id}/notifications/sms`
- `GET /organizations/{org_id}/notifications/sms/{id}`

## Credentials handling

Every value above is read via `api/config.py`'s `Settings` (which reads
`.env`, gitignored) — never hardcoded, never logged. `.env.example`
documents every variable with no real value. If real credentials were
ever pasted into a chat, terminal history, or any non-`.env` location,
rotate them — a value that has left `.env` should be treated as
potentially exposed regardless of where it was seen.
