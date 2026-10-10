"""The isolated preview server must refuse to start when anything points at a real service (incident of 2026-10-10: test accounts written to production)."""

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location("dev_isolated_server", Path(__file__).resolve().parent.parent / "scripts" / "dev_isolated_server.py")
server = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(server)  # imports nothing heavy at module level


def test_refuses_a_production_database_url():
    with pytest.raises(SystemExit, match="DATABASE_URL"):
        server.assert_local_environment({"DATABASE_URL": "postgresql+asyncpg://u:p@db.abcd.supabase.co:5432/postgres"})


@pytest.mark.parametrize("name", ["REDIS_URL", "CELERY_BROKER_URL", "S3_ENDPOINT_URL", "SENTRY_DSN", "STRIPE_SECRET_KEY", "RESEND_API_KEY", "DATABASE_URL_TRANSACTION"])
def test_refuses_any_external_service(name):
    with pytest.raises(SystemExit, match=name):
        server.assert_local_environment({name: "https://something.example.com/x"})


def test_accepts_sqlite_local_hosts_and_empty_values():
    server.assert_local_environment({"DATABASE_URL": "sqlite+aiosqlite:///C:/tmp/x.db", "REDIS_URL": "redis://localhost:6379/0", "SENTRY_DSN": ""})
    server.assert_local_environment({"CELERY_BROKER_URL": "redis://127.0.0.1:6379/1"})


def test_configure_environment_overrides_a_production_looking_environment_and_blanks_services():
    env = {
        "DATABASE_URL": "postgresql+asyncpg://u:p@db.abcd.supabase.co:5432/postgres",
        "DATABASE_URL_TRANSACTION": "postgresql+asyncpg://u:p@pooler.supabase.com:6543/postgres",
        "REDIS_URL": "rediss://default:secret@redis.render.com:6379", "STRIPE_SECRET_KEY": "sk_live_x", "RESEND_API_KEY": "re_x",
    }
    result = server.configure_environment("/tmp/preview.db", env)
    assert result["DATABASE_URL"].startswith("sqlite+aiosqlite:///")
    assert result["DATABASE_URL_TRANSACTION"] == "" and result["REDIS_URL"] == "" and result["STRIPE_SECRET_KEY"] == "" and result["RESEND_API_KEY"] == ""
