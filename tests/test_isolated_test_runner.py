"""The isolated test runner (scripts/run_isolated_tests.py): it must refuse anything that could reach a real service, and it must never
hand the child process a credential from the parent environment. Pure function tests: no database, Redis or network."""

import pytest

from external_skip_allowlist import EXTERNAL_SKIPS, external_category
from scripts.run_isolated_tests import IsolationRefused, build_test_environment

LOCAL_DB = "postgresql+asyncpg://user:pw@127.0.0.1:15432/rag_test_integration"


def _parent(**overrides):
    parent = {"PATH": "x", "RAG_TEST_DATABASE_URL": LOCAL_DB}
    parent.update(overrides)
    return {k: v for k, v in parent.items() if v is not None}


def test_a_local_throwaway_stack_is_accepted_and_wired_everywhere():
    env = build_test_environment(_parent())
    assert env["DATABASE_URL"] == env["DATABASE_URL_TRANSACTION"] == LOCAL_DB
    assert env["CELERY_BROKER_URL"].startswith("redis://127.0.0.1:") and env["S3_ENDPOINT_URL"].startswith("http://127.0.0.1:")
    assert env["RAG_STRICT_SKIPS"] == "1" and env["COOKIE_SECURE"] == "False"


@pytest.mark.parametrize(
    "overrides",
    [
        {"RAG_TEST_DATABASE_URL": None},
        {"RAG_TEST_DATABASE_URL": "postgresql+asyncpg://u:p@aws-0-eu.pooler.supabase.com:6543/postgres"},
        {"RAG_TEST_DATABASE_URL": "postgresql+asyncpg://u:p@db.internal.example.com:5432/rag_test_integration"},
        {"RAG_TEST_REDIS_URL": "redis://default:pw@eu1-example.upstash.io:6379"},
        {"RAG_TEST_S3_ENDPOINT": "https://example.r2.cloudflarestorage.com"},
    ],
)
def test_anything_that_is_not_local_is_refused_before_the_tests_start(overrides):
    with pytest.raises(IsolationRefused):
        build_test_environment(_parent(**overrides))


def test_a_local_database_without_a_throwaway_name_is_refused():
    with pytest.raises(IsolationRefused):
        build_test_environment(_parent(RAG_TEST_DATABASE_URL="postgresql+asyncpg://u:p@127.0.0.1:5432/postgres"))


def test_the_parent_environment_never_leaks_into_the_child():
    parent = _parent(
        DATABASE_URL="postgresql+asyncpg://u:p@db.prod.example.com:6543/postgres",
        DATABASE_URL_TRANSACTION="postgresql+asyncpg://u:p@pooler.prod.example.com:6543/postgres",
        STRIPE_SECRET_KEY="sk_live_not_a_real_key",
        PAYSTACK_SECRET_KEY="sk_live_not_a_real_key",
        ANTHROPIC_API_KEY="sk-ant-not-a-real-key",
        SENTRY_DSN="https://key@o0.ingest.sentry.io/1",
    )
    env = build_test_environment(parent)
    for name in ("STRIPE_SECRET_KEY", "PAYSTACK_SECRET_KEY", "ANTHROPIC_API_KEY", "SENTRY_DSN"):
        assert name not in env
    assert env["DATABASE_URL"] == LOCAL_DB and env["DATABASE_URL_TRANSACTION"] == LOCAL_DB
    assert env["RAG_ENV_FILE"].endswith("does-not-exist")


def test_the_destructive_database_must_be_marked_and_different():
    env = build_test_environment(_parent(RAG_TEST_PG_ROUNDTRIP_URL="postgresql+asyncpg://u:p@127.0.0.1:15432/rag_remediation_scratch"))
    assert env["RAG_DISPOSABLE_PG_CONFIRM"] == "rag_remediation_scratch"
    with pytest.raises(IsolationRefused):
        build_test_environment(_parent(RAG_TEST_PG_ROUNDTRIP_URL="postgresql+asyncpg://u:p@127.0.0.1:15432/rag_test_integration"))
    with pytest.raises(IsolationRefused):
        build_test_environment(_parent(RAG_TEST_PG_ROUNDTRIP_URL="postgresql+asyncpg://u:p@127.0.0.1:15432/orders"))
    with pytest.raises(IsolationRefused):
        build_test_environment(_parent(RAG_TEST_P0_PG_URL="postgresql+asyncpg://u:p@127.0.0.1:15432/rag_test_integration"))


def test_only_documented_external_dependencies_may_stay_skipped():
    assert external_category("needs a real STRIPE_SECRET_KEY and STRIPE_TEST_PRICE_ID (a real price_id)") == "payment-provider-sandbox"
    assert external_category("Live staging tests require RAG_STAGING_TESTS=YES and the guarded staging runner.") == "hosted-staging"
    for local_reason in (
        "DATABASE_URL is not reachable -- skipping Postgres integration tests",
        "Redis is not reachable at CACHE_REDIS_URL -- skipping cache tests",
        "real Tesseract binary not installed on this machine",
        "PostgreSQL tests not authorized: RAG_DISPOSABLE_PG_URL is not set",
        "No live Celery worker responded to a ping",
        "",
    ):
        assert external_category(local_reason) is None, local_reason
    assert len(EXTERNAL_SKIPS) == 5


def test_the_model_hub_is_only_switched_off_on_request():
    assert "HF_HUB_OFFLINE" not in build_test_environment(_parent())
    env = build_test_environment(_parent(RAG_TEST_HF_OFFLINE="1"))
    assert env["HF_HUB_OFFLINE"] == "1" and env["TRANSFORMERS_OFFLINE"] == "1"
    assert "HF_HUB_OFFLINE" not in build_test_environment(_parent(RAG_TEST_HF_OFFLINE="0"))


def test_the_webhook_capture_skip_reasons_are_documented_external_dependencies():
    import re
    from pathlib import Path

    for name in ("test_billing_stripe_live.py", "test_billing_paystack_live.py"):
        source = (Path(__file__).parent / name).read_text(encoding="utf-8")
        reason = "".join(re.findall(r'"([^"]*)"', re.search(r"_WEBHOOK_SKIP_REASON = \((.*?)\n\)", source, re.DOTALL).group(1)))
        assert external_category(reason) == "payment-provider-sandbox", name