"""The guard that keeps the test suite away from real databases and services (incident of 2026-10-10)."""

import _remote_guard
from _remote_guard import find_remote_services


def test_local_and_sqlite_settings_pass():
    values = {
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/rag_saas_test", "DATABASE_URL_TRANSACTION": "",
        "RATE_LIMIT_REDIS_URL": "redis://localhost:6379/2", "CELERY_BROKER_URL": "redis://127.0.0.1:6379/0", "S3_ENDPOINT_URL": "http://localhost:9000",
        "RESEND_API_KEY": "re_ci_placeholder_never_a_real_key",
    }
    assert find_remote_services(values) == []
    assert find_remote_services({"DATABASE_URL": "sqlite+aiosqlite:///:memory:"}) == []
    assert find_remote_services({}) == []


def test_a_supabase_database_is_refused():
    problems = find_remote_services({"DATABASE_URL": "postgresql+asyncpg://u:p@db.abcdefgh.supabase.co:5432/postgres"})
    assert len(problems) == 1 and "DATABASE_URL" in problems[0] and "supabase" in problems[0]
    assert "p@" not in problems[0] and ":p" not in problems[0]  # the message never echoes the password


def test_the_transaction_pooler_redis_and_s3_are_refused_too():
    problems = find_remote_services({
        "DATABASE_URL_TRANSACTION": "postgresql+asyncpg://u:p@aws-0-eu.pooler.supabase.com:6543/postgres",
        "RATE_LIMIT_REDIS_URL": "rediss://default:x@redis.example.com:6379", "S3_ENDPOINT_URL": "https://abc.supabase.co/storage/v1/s3",
    })
    assert {p.split(" ")[0] for p in problems} == {"DATABASE_URL_TRANSACTION", "RATE_LIMIT_REDIS_URL", "S3_ENDPOINT_URL"}


def test_a_real_looking_email_key_and_live_payment_keys_are_refused():
    problems = find_remote_services({"RESEND_API_KEY": "re_AbCdEf123456", "STRIPE_SECRET_KEY": "sk_live_x", "PAYSTACK_SECRET_KEY": "sk_test_ok"})
    assert any("RESEND_API_KEY" in p for p in problems) and any("STRIPE_SECRET_KEY" in p for p in problems)
    assert not any("PAYSTACK" in p for p in problems)  # a test key is fine


def test_the_ci_workflow_no_longer_hands_production_secrets_to_the_test_job():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    start = text.index("  backend-tests:")
    block = text[start:text.index("\n  backend-security:", start)]
    assert "secrets." not in block, "the backend-tests job must use throw-away values only"
    assert "pgvector/pgvector" in block and "alembic upgrade head" in block
    assert _remote_guard.LOCAL_HOSTS  # keep the module import used
