"""Phase 5 of the 2026-10-12 security audit: a Redis reached over the public internet must use TLS and a password (TEN-005 decision).

Messages of the Celery queue (arguments, results), rate-limit counters and cached answers go through Redis; whoever can write to the queue can run any task. Offline."""

import pytest
from pydantic import ValidationError

from api.config import Settings, _is_private_or_internal_host, settings


def _settings(**overrides):
    defaults = {
        "DATABASE_URL": settings.DATABASE_URL,
        "JWT_SECRET_KEY": settings.JWT_SECRET_KEY,
        "SESSION_MIDDLEWARE_SECRET": settings.SESSION_MIDDLEWARE_SECRET,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("ALLOW_INSECURE_BROKER", raising=False)


@pytest.mark.parametrize("name", ["CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "RATE_LIMIT_REDIS_URL", "CACHE_REDIS_URL"])
def test_a_public_redis_without_tls_is_refused(name):
    with pytest.raises(ValidationError) as refused:
        _settings(**{name: "redis://default:s3cret-pw@eu1-example-12345.upstash.io:6379"})
    assert name in str(refused.value) and "TLS" in str(refused.value)
    assert "s3cret-pw" not in str(refused.value)  # the message never echoes the password


def test_a_public_redis_over_tls_without_a_password_is_refused():
    with pytest.raises(ValidationError, match="without a password"):
        _settings(CELERY_BROKER_URL="rediss://eu1-example-12345.upstash.io:6379")


def test_a_public_redis_over_tls_with_a_password_is_accepted():
    assert _settings(CELERY_BROKER_URL="rediss://default:pw@eu1-example-12345.upstash.io:6379").CELERY_BROKER_URL.startswith("rediss://")


@pytest.mark.parametrize("url", [
    "redis://localhost:6379/0", "redis://127.0.0.1:6379/0", "redis://redis:6379/0", "redis://redis-master.rag.svc:6379/0",
    "redis://cache.internal:6379/0", "redis://10.0.3.7:6379/0", "redis://192.168.1.20:6379/0", "redis://[::1]:6379/0",
])
def test_private_and_internal_redis_hosts_keep_working_without_tls(url):
    assert _settings(CELERY_BROKER_URL=url).CELERY_BROKER_URL == url


def test_the_explicit_override_still_works(monkeypatch):
    monkeypatch.setenv("ALLOW_INSECURE_BROKER", "1")
    assert _settings(CELERY_BROKER_URL="redis://default:pw@eu1-example-12345.upstash.io:6379")


@pytest.mark.parametrize("host,expected", [("", True), ("redis", True), ("localhost", True), ("10.1.2.3", True), ("8.8.8.8", False), ("x.upstash.io", False)])
def test_the_host_classification(host, expected):
    assert _is_private_or_internal_host(host) is expected
