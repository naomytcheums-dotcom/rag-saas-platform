"""The test suite must never run against a real database or real external services.

Incident of 2026-10-10: the GitHub Actions job ran the suite with the repository secret DATABASE_URL (the real database) and real S3 / e-mail keys, and several
integration tests read and DELETED rows there (for instance every row of `jwt_signing_keys`). This module lists what is NOT local so that tests/conftest.py can
stop the run before a single test executes. Bypass on purpose with ALLOW_REMOTE_TEST_SERVICES=1 (never in CI)."""

from urllib.parse import urlparse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal", "postgres", "redis", "minio", ""}
URL_SETTINGS = ("DATABASE_URL", "DATABASE_URL_TRANSACTION", "RATE_LIMIT_REDIS_URL", "CACHE_REDIS_URL", "REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "S3_ENDPOINT_URL")


def _host(url: str) -> str:
    if not url or url.startswith("sqlite"):
        return ""
    return (urlparse(url).hostname or "").lower()


def find_remote_services(values: dict) -> list[str]:
    """Return a human-readable list of the settings that point outside this machine or hold what looks like a real secret."""
    problems = []
    for name in URL_SETTINGS:
        host = _host(str(values.get(name) or ""))
        if host not in LOCAL_HOSTS:
            problems.append(f"{name} points to a remote host ({host})")
    resend = str(values.get("RESEND_API_KEY") or "")
    if resend and "placeholder" not in resend.lower() and "ci-only" not in resend.lower():
        problems.append("RESEND_API_KEY looks like a real key (tests would send real e-mails)")
    for name in ("STRIPE_SECRET_KEY", "PAYSTACK_SECRET_KEY"):
        key = str(values.get(name) or "")
        if key and ("live" in key.lower()):
            problems.append(f"{name} is a live payment key")
    return problems
