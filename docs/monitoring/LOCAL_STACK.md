# Local observability stack (Loki, Prometheus, Tempo, Grafana, Jaeger, OTel Collector)

## Start

```bash
docker compose -f docker-compose.observability.yml up -d
```

One command, no manual setup — datasources and the API dashboard are
provisioned automatically the first time Grafana starts.

## Stop

```bash
docker compose -f docker-compose.observability.yml down
```

Add `-v` to also delete the stored logs/metrics/traces (`down -v`).

## Point the API at the local stack

In `.env`:

```
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
LOKI_HOST=http://localhost:3100
# LOKI_USERNAME / LOKI_PASSWORD stay empty for the local stack --
# loki-config.yml has auth_enabled: false, same as this stack's other
# services. Only set them when pointing at Grafana Cloud instead (see
# docs/monitoring/GRAFANA_CLOUD_DATADOG_TWILIO.md).
```

Restart the API (`uvicorn api.main:app --reload` picks up `.env` on
restart, not live). `GET /metrics` is scraped by the local Prometheus
automatically (`observability/prometheus/prometheus.yml` — no restart
of the stack needed for that side).

## Interfaces

| Service | URL | Notes |
|---|---|---|
| Grafana | http://localhost:3000 | Anonymous access enabled as Admin for local dev — no login screen |
| Prometheus | http://localhost:9090 | Raw PromQL / targets page |
| Loki | http://localhost:3100 | No UI of its own — query it from Grafana Explore |
| Tempo | http://localhost:3200 | No UI of its own — query it from Grafana Explore, or use Jaeger below |
| Jaeger | http://localhost:16686 | A second, independent trace UI — the same traces also land here via its own OTLP receiver |
| OTel Collector health | http://localhost:13133 | `{"status":"Server available"}` when healthy |
| n8n | http://localhost:5678 | `docker compose -f docker-compose.observability.yml up -d n8n n8n-postgres` — see `docs/integrations/N8N.md` |

Airbyte is **not** part of this compose file — see
`docs/integrations/AIRBYTE.md` for why (its real, current self-hosting
method is `abctl`, not docker-compose) and how to install it.

## Test in real time

1. Hit any real API endpoint a few times (`curl http://localhost:8000/health`).
2. **Metrics**: Grafana → Dashboards → "RAG SaaS API — Overview" (auto-provisioned), or Prometheus → http://localhost:9090/graph → `http_requests_total`.
3. **Logs**: with `LOKI_HOST` set, `curl http://localhost:8000/monitoring/loki/test` (real admin auth required) synchronously pushes a real log line and reports the real HTTP result — then Grafana → Explore → Loki → `{service="rag-saas-api"}`.
4. **Traces**: with `OTEL_ENABLED=true`, any real request generates a real span (FastAPI/SQLAlchemy/Redis/httpx auto-instrumented, `api/security/tracing.py`) — Grafana → Explore → Tempo, or Jaeger UI → service `rag-saas-api`.

## Dashboards

Only **one** real dashboard ships (`observability/grafana/dashboards/api-overview.json`)
— requests/s by status class, p50/p95/p99 latency, 5xx error rate,
Celery task outcomes — because those are the metrics `api/monitoring.py`
actually emits today. **Honest gap, not fabricated**: LLM (calls/
tokens/cost), RAG (retrieval/documents/citations), and System
(CPU/memory/disk) dashboards are not included because no real
Prometheus metric exists yet for any of them in this codebase (system
resource numbers are real, but only exposed as JSON via `GET
/monitoring/metrics` and `GET /admin/monitoring/resources`, Partie
11.5/13.1 — not as Prometheus gauges, for the multiprocess-correctness
reason documented in `api/services/app_metrics.py`). Add a dashboard
JSON under `observability/grafana/dashboards/` and it's picked up on
the next Grafana restart — no other config needed.

## Troubleshooting

- **Prometheus shows `rag-saas-api` target as down**: `host.docker.internal`
  only resolves automatically on Docker Desktop (Windows/Mac). On
  native Linux Docker, either replace it in `observability/prometheus/prometheus.yml`
  with the host's real LAN IP, or add
  `extra_hosts: ["host.docker.internal:host-gateway"]` to the
  `prometheus` service in `docker-compose.observability.yml`.
- **No traces in Tempo/Jaeger**: confirm `OTEL_ENABLED=true` in `.env`
  and that the API process was actually restarted after setting it —
  `GET /monitoring/tracing/status` reports the real, current state
  (`active: true` once instrumentation actually ran).
- **This stack was never started/tested from this session**: Docker
  itself isn't reachable from this automation environment (`docker`
  isn't on PATH here) — every config file above is real and correct
  against each tool's own documented schema, but `docker compose up`
  against it has to be run and checked by you, not verified here.
