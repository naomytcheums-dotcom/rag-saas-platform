"""P0 audit fix SEC-001 -- the SQL tool's tenant filter was escapable.

The tool used to render `WHERE (<user where>) AND organization_id = :organization_id`
and relied on a hand-written scan of `'` characters to keep the user text from
closing the parenthesis. PostgreSQL's `E'\\''` string (backslash escape) made that
scan and the database disagree, so

    SELECT id FROM documents WHERE E'\\'' IS NULL) OR (1=1) OR (E'\\'' IS NULL

rendered `... WHERE (E'\\'' IS NULL) OR (1=1) OR (E'\\'' IS NULL) AND organization_id = ...`
and (AND binding tighter than OR) returned every tenant's rows.

Two independent layers now hold: (1) the validator refuses every construct that
makes string literals ambiguous, (2) the tenant predicate lives in a derived
table (`FROM (SELECT * FROM t WHERE organization_id = :organization_id) AS t`)
the user text cannot reach. Layer 2 is proven against a real PostgreSQL when
P0_PG_TEST_URL points at a disposable `pytest_*` database (skipped otherwise)."""

import os
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import DBAPIError

from api.models.document import Document, DocumentStatus
from api.models.organization import Organization
from api.tools import sql_tool
from api.tools.sql_tool import SqlToolError, execute_sql_query, validate_sql_query

EXPLOIT = "SELECT id FROM documents WHERE E'\\'' IS NULL) OR (1=1) OR (E'\\'' IS NULL"


def _org(name):
    return Organization(name=name, slug=f"{name.lower()}-{uuid.uuid4().hex[:8]}")


def _doc(org_id, name):
    return Document(
        organization_id=org_id, name=name, file_key=f"documents/{uuid.uuid4()}/{name}",
        file_size=100, file_type="application/pdf", status=DocumentStatus.completed.value,
    )


# ------------------------------------------------------------------ validator: the exploit and its relatives


def test_the_exact_audited_exploit_is_rejected():
    with pytest.raises(SqlToolError):
        validate_sql_query(EXPLOIT)


_AMBIGUOUS_STRING_QUERIES = [
    "SELECT id FROM documents WHERE e'\\'' IS NULL",
    "SELECT name FROM documents WHERE name = E'x'",
    "SELECT name FROM documents WHERE (E'x' = name)",
    "SELECT name FROM documents WHERE name = 'a\\b'",
    "SELECT name FROM documents WHERE name = '\\'",
    "SELECT name FROM documents WHERE name = U&'\\0041'",
    "SELECT name FROM documents WHERE name = u&'x'",
    "SELECT name FROM documents WHERE name = $$x$$",
    "SELECT name FROM documents WHERE name = $tag$x$tag$",
    "SELECT name FROM documents WHERE name = $1",
    'SELECT "name" FROM documents',
    # A double-quoted identifier containing a quote used to hide a function call from the allow-list scan.
    "SELECT name FROM documents WHERE \"a'\" IS NULL OR pg_sleep(10) IS NULL OR \"b'\" IS NULL",
    "SELECT name FROM documents WHERE name = 'unterminated",
]


@pytest.mark.parametrize("query", _AMBIGUOUS_STRING_QUERIES)
def test_constructs_that_make_string_literals_ambiguous_are_rejected(query):
    with pytest.raises(SqlToolError):
        validate_sql_query(query)


@pytest.mark.parametrize("query", [
    "SELECT name FROM documents WHERE name = 'active'",  # ends in `e'` but is a plain string
    "SELECT name FROM documents WHERE name = 'e'",
    "SELECT name FROM documents WHERE name = 'it''s' OR name = 'e'",
    "SELECT name FROM documents WHERE name LIKE'x'",  # identifier ending in E directly before a quote is not an E-string
    "SELECT name FROM documents WHERE name = 'a & b' AND name <> 'Qu&'",
    "SELECT lower(name) FROM documents WHERE (name = 'a' OR name = 'b') AND file_size IN (1, 2) ORDER BY name LIMIT 5",
    "SELECT count(*) FROM documents",
])
def test_legitimate_queries_are_still_accepted(query):
    validate_sql_query(query)


# ------------------------------------------------------------------ SQLite: the derived-table construction


_ADVERSARIAL_WHERES = [
    "1=1 OR name IS NOT NULL",
    "name LIKE '%' OR 1=1",
    "(1=1) OR (1=1)",
    "NOT (name = 'nothing')",
    "organization_id IS NOT NULL",
    "file_size > 0 OR file_size <= 0",
]


async def test_nominal_query_still_returns_the_callers_rows(db_session):
    org = _org("Nominal")
    db_session.add(org)
    await db_session.flush()
    db_session.add_all([_doc(org.id, "alpha.pdf"), _doc(org.id, "beta.pdf")])
    await db_session.commit()

    rows = await execute_sql_query(db_session, "SELECT name FROM documents WHERE name <> 'beta.pdf' ORDER BY name", org.id)
    qualified = await execute_sql_query(db_session, "SELECT documents.name FROM documents WHERE documents.name = 'beta.pdf'", org.id)
    counted = await execute_sql_query(db_session, "SELECT count(*) AS n FROM documents", org.id)

    assert [r["name"] for r in rows] == ["alpha.pdf"]
    assert [r["name"] for r in qualified] == ["beta.pdf"]
    assert counted[0]["n"] == 2


@pytest.mark.parametrize("where", _ADVERSARIAL_WHERES)
async def test_adversarial_where_clauses_only_ever_see_the_callers_rows(db_session, where):
    org_a, org_b = _org("SqliteA"), _org("SqliteB")
    db_session.add_all([org_a, org_b])
    await db_session.flush()
    db_session.add_all([_doc(org_a.id, "a-doc.pdf"), _doc(org_b.id, "b-SECRET.pdf")])
    await db_session.commit()

    rows = await execute_sql_query(db_session, f"SELECT name, organization_id FROM documents WHERE {where}", org_a.id)

    assert [r["name"] for r in rows] == ["a-doc.pdf"]


async def test_the_exploit_is_rejected_before_any_sql_runs(db_session):
    org_a = _org("Exploit")
    db_session.add(org_a)
    await db_session.commit()

    with pytest.raises(SqlToolError):
        await execute_sql_query(db_session, EXPLOIT, org_a.id)


# ------------------------------------------------------------------ real PostgreSQL (disposable database only)


@pytest.fixture
async def pg_session():
    url = os.environ.get("P0_PG_TEST_URL")
    if not url:
        pytest.skip("P0_PG_TEST_URL not set -- PostgreSQL proof skipped")
    if "/pytest_" not in url or "127.0.0.1" not in url:
        pytest.fail("P0_PG_TEST_URL must target a disposable local 'pytest_*' database")
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
            yield session
    finally:
        await engine.dispose()


@pytest.fixture
async def pg_two_orgs(pg_session):
    org_a, org_b = _org("PgA"), _org("PgB")
    pg_session.add_all([org_a, org_b])
    await pg_session.flush()
    ids = (org_a.id, org_b.id)
    pg_session.add_all([_doc(org_a.id, "a-doc.pdf"), _doc(org_b.id, "b-SECRET-1.pdf"), _doc(org_b.id, "b-SECRET-2.pdf")])
    await pg_session.commit()
    try:
        yield SimpleNamespace(id=ids[0]), SimpleNamespace(id=ids[1])
    finally:
        await pg_session.rollback()
        await pg_session.execute(delete(Document).where(Document.organization_id.in_(ids)))
        await pg_session.execute(delete(Organization).where(Organization.id.in_(ids)))
        await pg_session.commit()


@pytest.mark.parametrize("where", _ADVERSARIAL_WHERES)
async def test_pg_adversarial_where_clauses_never_return_the_other_organizations_rows(pg_session, pg_two_orgs, where):
    org_a, _org_b = pg_two_orgs

    rows = await execute_sql_query(pg_session, f"SELECT name FROM documents WHERE {where}", org_a.id)

    assert [r["name"] for r in rows] == ["a-doc.pdf"]


async def test_pg_unfiltered_query_and_count_are_scoped_to_the_organization(pg_session, pg_two_orgs):
    org_a, org_b = pg_two_orgs

    assert [r["name"] for r in await execute_sql_query(pg_session, "SELECT name FROM documents", org_a.id)] == ["a-doc.pdf"]
    assert (await execute_sql_query(pg_session, "SELECT count(*) AS n FROM documents", org_b.id))[0]["n"] == 2


async def test_pg_exploit_is_rejected_by_the_validator(pg_session, pg_two_orgs):
    org_a, _org_b = pg_two_orgs

    with pytest.raises(SqlToolError):
        await execute_sql_query(pg_session, EXPLOIT, org_a.id)


async def test_pg_even_with_the_validator_bypassed_the_exploit_cannot_widen_the_tenant_filter(pg_session, pg_two_orgs, monkeypatch):
    """Layer 2 on its own: the audited string goes straight to PostgreSQL (the
    validator replaced by a pass-through that only does the shape match). The
    tenant predicate is inside the derived table, so the leftover user text
    cannot widen it -- PostgreSQL rejects the statement (unbalanced ')')."""
    org_a, _org_b = pg_two_orgs
    monkeypatch.setattr(sql_tool, "validate_sql_query", lambda q: sql_tool._QUERY_PATTERN.match(sql_tool.sanitize_sql_query(q)))

    with pytest.raises(DBAPIError):
        await execute_sql_query(pg_session, EXPLOIT, org_a.id)
    await pg_session.rollback()

    # The same mechanism with a well-formed boolean escape: still only the caller's rows.
    rows = await execute_sql_query(pg_session, "SELECT name FROM documents WHERE E'x' = E'x' OR (1=1)", org_a.id)
    assert [r["name"] for r in rows] == ["a-doc.pdf"]
