"""The test suite must never run against a real database or real external services.

Incident of 2026-10-10: the GitHub Actions job ran the suite with the repository secret DATABASE_URL (the real database) and real S3 / e-mail keys, and several
integration tests read and DELETED rows there (for instance every row of `jwt_signing_keys`). This module lists what is NOT local so that tests/conftest.py can
stop the run before a single test executes. Bypass on purpose with ALLOW_REMOTE_TEST_SERVICES=1 (never in CI)."""

import re
from urllib.parse import urlparse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal", "postgres", "redis", "minio", ""}
URL_SETTINGS = ("DATABASE_URL", "DATABASE_URL_TRANSACTION", "RATE_LIMIT_REDIS_URL", "CACHE_REDIS_URL", "REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "S3_ENDPOINT_URL")

# Hosted observability / alerting services: a test that switches tracing or logging on must never reach them (a span reached the production Tempo on 2026-10-11).
OBSERVABILITY_SETTINGS = ("LOKI_HOST", "TEMPO_HOST", "LANGFUSE_HOST", "SENTRY_DSN", "OTEL_EXPORTER_OTLP_ENDPOINT", "SECURITY_ALERT_WEBHOOK_URL")
# Paid providers: a test with one of these keys spends real money (two real Anthropic calls happened on 2026-10-11). The opt-in real-LLM run may keep them.
PAID_KEY_SETTINGS = (
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY", "OPENAI_EMBEDDING_API_KEY", "VOYAGE_API_KEY", "COHERE_API_KEY",
    "TAVILY_API_KEY", "DEEPGRAM_API_KEY", "GOOGLE_CLOUD_TTS_API_KEY", "ELEVENLABS_API_KEY", "WATSONX_API_KEY", "TWILIO_AUTH_TOKEN",
)
PAYMENT_KEY_SETTINGS = ("RESEND_API_KEY", "STRIPE_SECRET_KEY", "PAYSTACK_SECRET_KEY")
GUARDED_SETTINGS = (*URL_SETTINGS, *PAYMENT_KEY_SETTINGS, *OBSERVABILITY_SETTINGS, *PAID_KEY_SETTINGS)

# A database reached through a local port can still be a tunnel to the real one: a local host is not enough, the name must look disposable.
_DISPOSABLE_DATABASE_NAME = re.compile(r"(test|pytest|disposable|scratch|throwaway|tmp)", re.IGNORECASE)
DATABASE_NAME_SETTINGS = ("DATABASE_URL", "DATABASE_URL_TRANSACTION")


def _host(url: str) -> str:
    if not url or url.startswith("sqlite"):
        return ""
    return (urlparse(url).hostname or "").lower()


def _service_host(value: str) -> str:
    """Host of a setting that may be a bare host name (LOKI_HOST=logs-prod.example.net) or a DSN, not only a URL with a scheme."""
    value = value.strip()
    if not value:
        return ""
    return (urlparse(value if "://" in value else f"//{value}").hostname or "").lower()


def _database_name(url: str) -> str:
    return urlparse(url.replace("+asyncpg", "")).path.lstrip("/")


def _looks_like_a_real_key(value: str) -> bool:
    lowered = value.lower()
    return bool(value) and "placeholder" not in lowered and "ci-only" not in lowered


def find_remote_services(values: dict, allow_paid_keys: bool = False) -> list[str]:
    """Return a human-readable list of the settings that point outside this machine or hold what looks like a real secret.
    `allow_paid_keys` is only for the opt-in real-LLM run (RUN_REAL_LLM_TESTS=1)."""
    problems = []
    for name in URL_SETTINGS:
        raw = str(values.get(name) or "")
        host = _host(raw)
        if host not in LOCAL_HOSTS:
            problems.append(f"{name} points to a remote host ({host})")
        elif name in DATABASE_NAME_SETTINGS and raw and not raw.startswith("sqlite") and not _DISPOSABLE_DATABASE_NAME.search(_database_name(raw)):
            problems.append(f"{name} is a local database whose name does not look disposable (it must contain test, pytest, disposable, scratch, throwaway or tmp: a tunnel to a real database is local too)")
    for name in OBSERVABILITY_SETTINGS:
        host = _service_host(str(values.get(name) or ""))
        if host not in LOCAL_HOSTS:
            problems.append(f"{name} points to a hosted service ({host})")
    if not allow_paid_keys:
        for name in PAID_KEY_SETTINGS:
            if _looks_like_a_real_key(str(values.get(name) or "")):
                problems.append(f"{name} holds a key (the tests would spend real money)")
    resend = str(values.get("RESEND_API_KEY") or "")
    if resend and "placeholder" not in resend.lower() and "ci-only" not in resend.lower():
        problems.append("RESEND_API_KEY looks like a real key (tests would send real e-mails)")
    for name in ("STRIPE_SECRET_KEY", "PAYSTACK_SECRET_KEY"):
        key = str(values.get(name) or "")
        if key and ("live" in key.lower()):
            problems.append(f"{name} is a live payment key")
    return problems
