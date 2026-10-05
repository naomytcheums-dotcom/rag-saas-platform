"""Network-free regressions for asyncpg-to-libpq URL conversion."""

import pytest
from psycopg2.extensions import make_dsn, parse_dsn
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url

from api.database_url import synchronous_database_url

_ASYNC_URL = "postgresql+asyncpg://test:unit-test-only@localhost:5432/test_db"
_SSL_MODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")


@pytest.mark.parametrize("mode", _SSL_MODES)
def test_asyncpg_ssl_becomes_the_identical_libpq_sslmode(mode):
    original = make_url(f"{_ASYNC_URL}?ssl={mode}&application_name=task")
    result = synchronous_database_url(original)

    assert isinstance(result, URL)
    assert result.drivername == "postgresql+psycopg2"
    assert dict(result.query) == {"sslmode": mode, "application_name": "task"}
    assert dict(original.query) == {"ssl": mode, "application_name": "task"}
    engine = create_engine(result)
    try:
        args, kwargs = engine.dialect.create_connect_args(result)
        assert args == []
        # libpq parses this locally, detecting invalid options without connecting.
        assert parse_dsn(make_dsn(**kwargs))["sslmode"] == mode
    finally:
        engine.dispose()


def test_conversion_preserves_escaped_credentials_and_query_mapping():
    original = make_url(
        "postgresql+asyncpg://user%40%2Basyncpg:p%40ss%3A%2F%25%2Basyncpg"
        "@localhost:6543/test_db?ssl=verify-full&sslrootcert=C%3A%5Ccerts%5Croot.pem"
        "&application_name=worker%2Basyncpg&options=-c%20search_path%3Dtenant"
        "&options=-c%20statement_timeout%3D1000"
    )
    result = synchronous_database_url(original.render_as_string(hide_password=False))

    assert result.username == original.username == "user@+asyncpg"
    assert result.password == original.password == "p@ss:/%+asyncpg"
    assert (result.host, result.port, result.database) == (original.host, original.port, original.database)
    assert dict(result.query) == {
        **{key: value for key, value in original.query.items() if key != "ssl"},
        "sslmode": "verify-full",
    }
    assert make_url(result.render_as_string(hide_password=False)) == result


def test_allowlisted_staging_url_converts_without_connecting(monkeypatch):
    from scripts.staging_target import validate_staging_url

    monkeypatch.setenv("STAGING_ALLOWED_DIRECT_HOST", "db.example-ref.supabase.co")
    monkeypatch.setenv("STAGING_ALLOWED_POOLER_HOST", "staging-pooler.example.invalid")
    monkeypatch.setenv("STAGING_ALLOWED_POOLER_USER", "postgres.example-ref")
    url = validate_staging_url(
        "postgresql://postgres.example-ref:unit-test-only@staging-pooler.example.invalid:5432/postgres",
    )
    result = synchronous_database_url(url)
    assert result.host == "staging-pooler.example.invalid"
    assert result.username == "postgres.example-ref"
    assert dict(result.query) == {"sslmode": "require"}


@pytest.mark.parametrize("driver", ("postgresql", "postgresql+asyncpg", "postgresql+psycopg2"))
def test_absent_ssl_does_not_invent_or_disable_tls(driver):
    original = make_url(_ASYNC_URL).set(drivername=driver, query={"application_name": "worker"})
    result = synchronous_database_url(original)

    assert result == original.set(drivername="postgresql+psycopg2")
    assert synchronous_database_url(result) == result


@pytest.mark.parametrize("mode", _SSL_MODES)
def test_existing_sslmode_and_matching_alias_are_preserved(mode):
    original = make_url(_ASYNC_URL).set(query={"sslmode": mode, "sslrootcert": "root.pem"})
    assert synchronous_database_url(original).query == original.query
    assert synchronous_database_url(original.update_query_dict({"ssl": mode})).query == original.query


@pytest.mark.parametrize("query", [
    {"ssl": "require", "sslmode": "disable"},
    {"ssl": "verify-full", "sslmode": "require"},
    {"ssl": "require", "sslmode": "verify-full"},
    {"ssl": ("require", "disable")},
    {"sslmode": ("verify-full", "require")},
    {"ssl": ""},
    {"ssl": "unknown"},
    {"sslmode": "unknown"},
])
def test_invalid_or_conflicting_ssl_options_fail_closed(query):
    with pytest.raises(ValueError, match="SSL mode|Conflicting"):
        synchronous_database_url(make_url(_ASYNC_URL).set(query=query))


def test_non_postgresql_url_is_rejected():
    with pytest.raises(ValueError, match="PostgreSQL URL"):
        synchronous_database_url("sqlite:///:memory:")


def test_task_consumers_share_the_driver_safe_engine():
    from api.config import settings
    from api.tasks import (
        account_deletion_reminder,
        account_purge,
        jwt_key_rotation,
        token_blacklist_cleanup,
    )
    from api.tasks._sync_engine import sync_engine

    assert sync_engine.url == synchronous_database_url(settings.DATABASE_URL)
    for module in (account_deletion_reminder, account_purge, jwt_key_rotation, token_blacklist_cleanup):
        assert module._sync_engine is sync_engine


def test_system_logging_uses_the_same_url_conversion(monkeypatch):
    from api.config import settings
    from api.security import system_log_handler

    original = make_url(_ASYNC_URL).set(query={"ssl": "verify-full", "sslrootcert": "root.pem"})
    monkeypatch.setattr(settings, "DATABASE_URL", original.render_as_string(hide_password=False))
    monkeypatch.setattr(system_log_handler, "_sync_engine", None)
    engine = system_log_handler._get_sync_engine()
    try:
        assert engine.url == synchronous_database_url(original)
        args, kwargs = engine.dialect.create_connect_args(engine.url)
        assert args == []
        assert parse_dsn(make_dsn(**kwargs))["sslmode"] == "verify-full"
        assert engine is system_log_handler._get_sync_engine()
    finally:
        engine.dispose()
