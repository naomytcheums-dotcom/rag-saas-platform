#!/usr/bin/env python
"""Real validation of 10.3.6 / 13.5.5 (LLM traces) against the trace backend the settings select (Langfuse, Grafana Tempo, any OTLP collector, Datadog).

    # OTLP / Langfuse / Tempo, as configured for the application:
    RUN_LIVE_VENDOR_VALIDATION=1 OTEL_ENABLED=true OTEL_EXPORTER_OTLP_ENDPOINT=https://collector.example.com:4318 python scripts/validate_tracing_live.py
    RUN_LIVE_VENDOR_VALIDATION=1 OTEL_ENABLED=true LANGFUSE_HOST=https://cloud.langfuse.com LANGFUSE_PUBLIC_KEY=pk-... LANGFUSE_SECRET_KEY=sk-... python scripts/validate_tracing_live.py
    RUN_LIVE_VENDOR_VALIDATION=1 OTEL_ENABLED=true TEMPO_HOST=... TEMPO_USERNAME=... TEMPO_PASSWORD=... python scripts/validate_tracing_live.py
    # Datadog LLM Observability (needs `pip install ddtrace`):
    RUN_LIVE_VENDOR_VALIDATION=1 DD_API_KEY=... DD_SITE=datadoghq.com python scripts/validate_tracing_live.py

Sets up tracing with the product's `setup_tracing`, emits one GenAI span named "chat validation-model" (the shape llm_providers.py emits for every completion),
flushes, and requires that the exporter reported no failure (the OTLP exporter logs a failed export; a 401/404/5xx from the backend is caught here). The span
is then visible in the backend under the service name "rag-validation".
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _live_vendor as live  # noqa: E402


class _Failures(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record):
        text = record.getMessage()
        if "export" in text.lower() or "failed" in text.lower():
            self.messages.append(text[:300])


async def main() -> int:
    live.require_opt_in("your trace backend / Datadog", "one span, free")
    report = live.Report("llm_traces")
    os.environ.setdefault("OTEL_SERVICE_NAME", "rag-validation")
    os.environ.setdefault("OTEL_TRACES_SAMPLER_ARG", "1.0")
    configured_otlp = any(live.have(*names) for names in (("OTEL_EXPORTER_OTLP_ENDPOINT",), ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"), ("TEMPO_HOST", "TEMPO_USERNAME", "TEMPO_PASSWORD")))
    if configured_otlp and os.environ.get("OTEL_ENABLED", "").lower() == "true":
        tracing = live.product("api.security.tracing")
        failures = _Failures()
        logging.getLogger().addHandler(failures)

        async def otlp():
            from opentelemetry import trace

            tracing.setup_tracing(None)
            assert tracing.tracing_status()["active"], "setup_tracing() did not activate tracing"
            with trace.get_tracer("rag-validation").start_as_current_span("chat validation-model") as span:
                span.set_attribute("gen_ai.operation.name", "chat")
                span.set_attribute("gen_ai.system", "validation")
                span.set_attribute("gen_ai.request.model", "validation-model")
                span.set_attribute("gen_ai.usage.input_tokens", 1)
                span.set_attribute("gen_ai.usage.output_tokens", 1)
            provider = trace.get_tracer_provider()
            provider.force_flush(15000)
            provider.shutdown()
            assert not failures.messages, failures.messages
            return {"exporter": tracing.tracing_status()["exporter"]}

        await report.check("otlp", otlp)
    else:
        report.skipped("otlp", "set OTEL_ENABLED=true plus OTEL_EXPORTER_OTLP_ENDPOINT, or LANGFUSE_*, or TEMPO_*")

    if live.have("DD_API_KEY"):
        datadog = live.product("api.security.datadog_llmobs")

        async def dd():
            try:
                import ddtrace  # noqa: F401
            except ImportError as exc:
                raise RuntimeError("ddtrace is not installed in this environment (pip install ddtrace)") from exc
            assert datadog.setup_llm_observability(), "LLMObs.enable() failed"
            from ddtrace.llmobs import LLMObs

            with LLMObs.llm(model_name="validation-model", model_provider="validation", name="rag-validation") as span:
                LLMObs.annotate(span=span, input_data="ping", output_data="pong")
            LLMObs.flush()
            return datadog.llm_observability_status()

        await report.check("datadog", dd)
    else:
        report.skipped("datadog", "DD_API_KEY is not in the process environment")
    return report.finish()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
