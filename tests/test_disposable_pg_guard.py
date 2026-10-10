"""R3: the guard that decides whether the PostgreSQL concurrency tests may touch a database. Pure function, no database needed."""

import pytest

from disposable_pg_guard import disposable_pg_refusal

GOOD = "postgresql+asyncpg://u:p@127.0.0.1:15432/rag_sec_roundtrip"
OTHER_DATABASE_URL = "postgresql+asyncpg://postgres:x@db.example.com:5432/postgres"


def test_the_local_roundtrip_database_is_accepted_with_its_confirmation():
    assert disposable_pg_refusal(GOOD, "rag_sec_roundtrip", OTHER_DATABASE_URL) is None


@pytest.mark.parametrize("name", ["rag_disposable_1", "scratch_db", "throwaway", "RAG_ROUNDTRIP", "my_disposable_pg_test"])
def test_every_accepted_marker_works(name):
    assert disposable_pg_refusal(f"postgresql+asyncpg://u:p@localhost:5432/{name}", name, OTHER_DATABASE_URL) is None


@pytest.mark.parametrize("url", [
    "postgresql+asyncpg://u:p@localhost:5432/prod_replica_tunnel",
    "postgresql+asyncpg://u:p@localhost:6543/postgres",
    "postgresql+asyncpg://u:p@localhost:5432/",
    "postgresql+asyncpg://u:p@localhost:5432",
])
def test_a_local_database_without_a_disposable_marker_is_refused_even_when_confirmed(url):
    name = url.rsplit("/", 1)[-1]
    assert disposable_pg_refusal(url, name, OTHER_DATABASE_URL) is not None


def test_the_confirmation_is_mandatory_and_must_match_the_database_name():
    assert disposable_pg_refusal(GOOD, None, OTHER_DATABASE_URL) is not None
    assert disposable_pg_refusal(GOOD, "", OTHER_DATABASE_URL) is not None
    assert disposable_pg_refusal(GOOD, "rag_other_roundtrip", OTHER_DATABASE_URL) is not None


@pytest.mark.parametrize("url", [
    "postgresql+asyncpg://u:p@db.example.com:5432/rag_roundtrip",
    "postgresql+asyncpg://u:p@[::1]:5432/rag_roundtrip",
    "postgresql+asyncpg://u:p@10.0.0.5:5432/rag_roundtrip",
    "",
])
def test_a_non_local_or_missing_url_is_refused(url):
    assert disposable_pg_refusal(url, "rag_roundtrip", OTHER_DATABASE_URL) is not None


def test_the_target_must_differ_from_the_applications_database_url():
    same = "postgresql+asyncpg://isolated:isolated@127.0.0.1:15432/rag_sec_roundtrip"
    assert disposable_pg_refusal(GOOD, "rag_sec_roundtrip", same) is not None, "same host, port and database"
    default_port = "postgresql+asyncpg://a:b@localhost/rag_roundtrip"
    explicit_port = "postgresql+asyncpg://c:d@127.0.0.1:5432/rag_roundtrip"
    assert disposable_pg_refusal(explicit_port, "rag_roundtrip", default_port) is not None, "localhost == 127.0.0.1 and 5432 is the default port"


def test_the_refusal_never_contains_the_password():
    reason = disposable_pg_refusal("postgresql+asyncpg://u:s3cr3t-pass@localhost:5432/postgres", "postgres", OTHER_DATABASE_URL)
    assert reason and "s3cr3t-pass" not in reason
