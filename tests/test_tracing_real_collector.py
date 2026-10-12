"""Audit items 10.3.5 / 13.5.4 (distributed tracing): spans really reach a collector, opt-in.

tests/test_tracing*.py check the wiring with fakes. This file starts the application's own `setup_tracing`, sends a request through an
instrumented FastAPI app and reads the trace back from a REAL Jaeger (OTLP over HTTP, the exporter the application uses). Skipped unless
OTEL_REAL_TEST_JAEGER is set, for example

    docker run -d --name rag-test-jaeger -p 127.0.0.1:16686:16686 -p 127.0.0.1:4318:4318 jaegertracing/all-in-one:1.76.0
    OTEL_REAL_TEST_JAEGER=http://127.0.0.1 pytest tests/test_tracing_real_collector.py

It runs in its own process because the OpenTelemetry tracer provider is global and can only be installed once."""

import os
import time
import uuid

import httpx
import pytest
from fastapi import FastAPI

from api.config import settings
from api.security import tracing

JAEGER = os.environ.get("OTEL_REAL_TEST_JAEGER", "").rstrip("/")

pytestmark = pytest.mark.skipif(not JAEGER, reason="OTEL_REAL_TEST_JAEGER is not set (no real collector to export to)")


def _traces_for(service: str) -> list[dict]:
    response = httpx.get(f"{JAEGER}:16686/api/traces", params={"service": service, "limit": 20}, timeout=10)
    response.raise_for_status()
    return response.json().get("data") or []


async def test_a_request_through_the_instrumented_app_arrives_in_jaeger(monkeypatch):
    service = f"rag-saas-test-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(settings, "OTEL_SERVICE_NAME", service)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", f"{JAEGER}:4318")
    monkeypatch.setattr(settings, "OTEL_TRACES_SAMPLER_ARG", 1.0)
    monkeypatch.setattr(tracing, "_instrumented", False)
    # setup_tracing prefers Langfuse, then Grafana Cloud Tempo, over the plain collector endpoint: a developer .env that carries those
    # credentials would send this test's span to a hosted service. Force them off, and refuse to run if they are still set.
    for hosted in ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "TEMPO_HOST", "TEMPO_USERNAME", "TEMPO_PASSWORD"):
        monkeypatch.setattr(settings, hosted, None)
    assert not (settings.TEMPO_HOST or settings.LANGFUSE_HOST)

    app = FastAPI()

    @app.get("/ping-for-trace")
    async def ping():
        return {"ok": True}

    tracing.setup_tracing(app)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        assert (await client.get("/ping-for-trace")).status_code == 200

    from opentelemetry import trace

    provider = trace.get_tracer_provider()
    assert provider.force_flush(10_000), "the exporter did not flush in time"

    traces = []
    for _ in range(20):  # Jaeger indexes asynchronously
        traces = _traces_for(service)
        if traces:
            break
        time.sleep(0.5)
    assert traces, "no trace for this service reached Jaeger"
    operations = {span["operationName"] for trace_data in traces for span in trace_data["spans"]}
    assert any("ping-for-trace" in operation for operation in operations), operations
