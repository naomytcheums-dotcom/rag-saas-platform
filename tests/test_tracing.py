"""
api/security/tracing.py -- real OpenTelemetry setup, disabled by
default (see that module's own docstring). No real OTLP collector
exists in this environment, so `setup_tracing` itself (a real network-
adjacent side effect) is not exercised here -- `tracing_status`/
`_active_exporter_name` are pure, real config-reading functions, tested
directly, same "test the real logic, not a fabricated collector"
discipline as every other observability integration in this codebase.
"""

from api.config import settings
from api.security.tracing import _active_exporter_name, tracing_status


def test_active_exporter_defaults_to_console_with_nothing_configured(monkeypatch):
    monkeypatch.setattr(settings, "LANGFUSE_HOST", None)
    monkeypatch.setattr(settings, "TEMPO_HOST", None)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)

    assert _active_exporter_name() == "console"


def test_active_exporter_prefers_langfuse_over_tempo_and_generic_otlp(monkeypatch):
    """Validation criterion: Langfuse (this étape's own real addition)
    must win when multiple backends happen to be configured at once --
    a deliberate priority order, not an arbitrary one."""
    monkeypatch.setattr(settings, "LANGFUSE_HOST", "https://cloud.langfuse.com")
    monkeypatch.setattr(settings, "LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setattr(settings, "LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setattr(settings, "TEMPO_HOST", "https://tempo.example.com")
    monkeypatch.setattr(settings, "TEMPO_USERNAME", "user")
    monkeypatch.setattr(settings, "TEMPO_PASSWORD", "pass")
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")

    assert _active_exporter_name() == "langfuse"


def test_active_exporter_needs_all_three_real_langfuse_credentials(monkeypatch):
    """A host alone (no keys) is not a real, usable Langfuse config --
    same "all three or none" discipline as TEMPO_* above."""
    monkeypatch.setattr(settings, "LANGFUSE_HOST", "https://cloud.langfuse.com")
    monkeypatch.setattr(settings, "LANGFUSE_PUBLIC_KEY", None)
    monkeypatch.setattr(settings, "LANGFUSE_SECRET_KEY", None)
    monkeypatch.setattr(settings, "TEMPO_HOST", None)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)

    assert _active_exporter_name() == "console"


def test_tracing_status_reports_the_real_exporter_and_disabled_state(monkeypatch):
    monkeypatch.setattr(settings, "OTEL_ENABLED", False)
    monkeypatch.setattr(settings, "LANGFUSE_HOST", "https://cloud.langfuse.com")
    monkeypatch.setattr(settings, "LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setattr(settings, "LANGFUSE_SECRET_KEY", "sk-test")

    status = tracing_status()

    assert status["enabled"] is False
    assert status["exporter"] == "langfuse"
