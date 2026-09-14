# Observability Stack

Full detail: [`docs/monitoring/LOCAL_STACK.md`](../monitoring/LOCAL_STACK.md),
[`docs/monitoring/GRAFANA_CLOUD_DATADOG_TWILIO.md`](../monitoring/GRAFANA_CLOUD_DATADOG_TWILIO.md),
[`docs/monitoring/PARTIE_13_OBSERVABILITY.md`](../monitoring/PARTIE_13_OBSERVABILITY.md).

## Local stack

```bash
docker compose -f docker-compose.observability.yml up -d
```

Runs a local monitoring stack for development/self-hosted use without
depending on a third-party SaaS.

## Managed (Grafana Cloud / Datadog)

For production, point the platform at Grafana Cloud (Loki for logs,
Tempo for traces) and/or Datadog LLM Observability instead of the local
stack — set the corresponding variables from `.env.example`'s
monitoring section, see [Environment Variables](ENVIRONMENT.md).

## What's monitored

Request/error rates, background job health (Celery), and LLM-specific
observability (token usage, latency, cost) via Datadog LLM
Observability where configured — complementing the platform's own
in-app [Audit Logs](../admin/AUDIT_LOGS.md) and
[Quality Dashboard](../admin/DASHBOARD.md).
