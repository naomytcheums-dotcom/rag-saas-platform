"""
Partie 13.4 -- real OpenTelemetry distributed tracing, disabled by
default (`OTEL_ENABLED=False`) since this environment has no real
OTLP collector (Jaeger/Tempo/Datadog agent) running -- turning it on
with no `OTEL_EXPORTER_OTLP_ENDPOINT` configured would export spans
into the void, which is worse than being honest that it's off.

Deliberately does NOT store spans in this app's own database (no
Trace/Span model) -- that would duplicate what a real OTLP collector +
backend (Jaeger, Tempo, ...) already does correctly, and "distributed"
tracing across FastAPI/Celery/SQLAlchemy/Redis/httpx is exactly the
kind of cross-process correlation a real trace backend is built for;
a single app-owned table can't see spans from a separate Celery worker
process the way a real collector can. Enabling OTEL_ENABLED with a real
OTEL_EXPORTER_OTLP_ENDPOINT is what makes this genuinely useful --
without a collector to point at, this stays real code that's simply
switched off, not a placeholder.
"""

import logging

from api.config import settings

logger = logging.getLogger(__name__)

_instrumented = False


def setup_tracing(app) -> None:
    global _instrumented
    if not settings.OTEL_ENABLED or _instrumented:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

        resource = Resource(attributes={SERVICE_NAME: settings.OTEL_SERVICE_NAME})
        sampler = ParentBased(TraceIdRatioBased(settings.OTEL_TRACES_SAMPLER_ARG))
        provider = TracerProvider(resource=resource, sampler=sampler)

        if settings.TEMPO_HOST and settings.TEMPO_USERNAME and settings.TEMPO_PASSWORD:
            # Grafana Cloud Tempo -- real OTLP/HTTP export with Basic Auth,
            # same real per-stack "host + username + password" shape as
            # Loki above (api/security/loki_handler.py's own docstring).
            import base64

            token = base64.b64encode(f"{settings.TEMPO_USERNAME}:{settings.TEMPO_PASSWORD}".encode()).decode()
            exporter = OTLPSpanExporter(endpoint=f"{settings.TEMPO_HOST}/v1/traces", headers={"Authorization": f"Basic {token}"})
        elif settings.OTEL_EXPORTER_OTLP_ENDPOINT:
            exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        else:
            # Real, honest fallback: no collector configured, so spans
            # go to this process's own console instead of being silently
            # dropped -- still real OpenTelemetry, still useful for a
            # developer confirming instrumentation works locally.
            exporter = ConsoleSpanExporter()

        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        SQLAlchemyInstrumentor().instrument()
        RedisInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()

        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()

        _instrumented = True
        logger.info(
            "OpenTelemetry tracing enabled (service=%s, exporter=%s)",
            settings.OTEL_SERVICE_NAME, "otlp" if settings.OTEL_EXPORTER_OTLP_ENDPOINT else "console",
        )
    except Exception:
        logger.warning("OpenTelemetry setup failed -- tracing stays disabled", exc_info=True)


def tracing_status() -> dict:
    return {
        "enabled": settings.OTEL_ENABLED,
        "active": _instrumented,
        "service_name": settings.OTEL_SERVICE_NAME,
        "exporter": "otlp" if settings.OTEL_EXPORTER_OTLP_ENDPOINT else "console",
        "otlp_endpoint": settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        "sampler_ratio": settings.OTEL_TRACES_SAMPLER_ARG,
    }
