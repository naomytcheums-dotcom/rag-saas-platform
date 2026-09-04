"""Partie 5.2.4 -- SQL tool. Real SQLite execution for execute_sql_query
(no mocking); validation/formatting are pure functions, tested
directly."""

import uuid

import pytest

from api.config import settings
from api.models.document import Document, DocumentStatus
from api.models.organization import Organization
from api.tools.sql_tool import (
    SqlToolError, execute_sql_query, format_sql_results, get_sql_schema, sanitize_sql_query, validate_sql_query,
)


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_document(db_session, org_id, name="doc.pdf"):
    document = Document(
        organization_id=org_id, name=name, file_key=f"documents/{uuid.uuid4()}/{name}",
        file_size=100, file_type="application/pdf", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    return document


# --------------------------------------- sanitize_sql_query --


def test_sanitize_sql_query_strips_whitespace_and_trailing_semicolon():
    assert sanitize_sql_query("  SELECT name FROM documents;  ") == "SELECT name FROM documents"


# --------------------------------------- validate_sql_query --


def test_validate_sql_query_accepts_a_real_simple_select():
    """Validation criterion: la validation fonctionne."""
    match = validate_sql_query("SELECT name FROM documents WHERE name = 'x' ORDER BY name LIMIT 5")
    assert match.group("table") == "documents"


def test_validate_sql_query_rejects_too_long_a_query(monkeypatch):
    monkeypatch.setattr(settings, "SQL_TOOL_MAX_QUERY_LENGTH", 10)
    with pytest.raises(SqlToolError, match="maximum length"):
        validate_sql_query("SELECT name FROM documents")


def test_validate_sql_query_rejects_multiple_statements():
    """Validation criterion: sécurité -- injection SQL via chaînage de
    requêtes rejetée."""
    with pytest.raises(SqlToolError, match="single statement"):
        validate_sql_query("SELECT name FROM documents; DROP TABLE documents")


def test_validate_sql_query_rejects_sql_comments():
    with pytest.raises(SqlToolError, match="comments"):
        validate_sql_query("SELECT name FROM documents -- WHERE 1=1")


@pytest.mark.parametrize("keyword", ["INSERT INTO documents VALUES (1)", "UPDATE documents SET name='x'", "DELETE FROM documents", "DROP TABLE documents"])
def test_validate_sql_query_rejects_real_write_statements(keyword):
    """Validation criterion: sécurité -- les requêtes en écriture sont
    rejetées (outil en lecture seule)."""
    with pytest.raises(SqlToolError):
        validate_sql_query(keyword)


def test_validate_sql_query_rejects_a_real_subquery():
    with pytest.raises(SqlToolError, match="Subqueries"):
        validate_sql_query("SELECT (SELECT name FROM documents) FROM documents")


def test_validate_sql_query_rejects_join():
    with pytest.raises(SqlToolError, match="JOIN"):
        validate_sql_query("SELECT d.name FROM documents d JOIN document_chunks c ON c.document_id = d.id")


def test_validate_sql_query_rejects_an_unknown_table():
    with pytest.raises(SqlToolError, match="allowlist"):
        validate_sql_query("SELECT * FROM users")


def test_validate_sql_query_rejects_a_malformed_query():
    with pytest.raises(SqlToolError, match="does not start with SELECT"):
        validate_sql_query("not even sql")


def test_validate_sql_query_rejects_an_unsupported_but_select_shaped_query():
    with pytest.raises(SqlToolError, match="does not match"):
        validate_sql_query("SELECT name FROM documents GROUP BY name")


def test_validate_sql_query_rejects_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "SQL_TOOL_ENABLED", False)
    with pytest.raises(SqlToolError, match="disabled"):
        validate_sql_query("SELECT name FROM documents")


# --------------------------------------- execute_sql_query --


async def test_execute_sql_query_returns_real_rows(db_session):
    """Validation criterion: l'exécution SQL fonctionne."""
    org = await _make_org(db_session, "SQL Tool Org")
    await _make_document(db_session, org.id, name="alpha.pdf")
    await _make_document(db_session, org.id, name="beta.pdf")
    await db_session.commit()

    rows = await execute_sql_query(db_session, "SELECT name FROM documents ORDER BY name", org.id)
    assert [r["name"] for r in rows] == ["alpha.pdf", "beta.pdf"]


async def test_execute_sql_query_never_returns_another_organizations_rows(db_session):
    """Validation criterion: sécurité -- isolation multi-tenant réelle."""
    org_a = await _make_org(db_session, "SQL Org A")
    org_b = await _make_org(db_session, "SQL Org B")
    await _make_document(db_session, org_a.id, name="a-doc.pdf")
    await _make_document(db_session, org_b.id, name="b-doc.pdf")
    await db_session.commit()

    rows = await execute_sql_query(db_session, "SELECT name FROM documents", org_a.id)
    assert [r["name"] for r in rows] == ["a-doc.pdf"]


async def test_execute_sql_query_combines_a_real_where_clause_with_the_org_filter(db_session):
    org = await _make_org(db_session, "SQL Where Org")
    await _make_document(db_session, org.id, name="match.pdf")
    await _make_document(db_session, org.id, name="other.pdf")
    await db_session.commit()

    rows = await execute_sql_query(db_session, "SELECT name FROM documents WHERE name = 'match.pdf'", org.id)
    assert [r["name"] for r in rows] == ["match.pdf"]


async def test_execute_sql_query_respects_the_real_row_cap(db_session, monkeypatch):
    """Validation criterion: les limites sont respectées."""
    monkeypatch.setattr(settings, "SQL_TOOL_MAX_ROWS", 1)
    org = await _make_org(db_session, "SQL Cap Org")
    await _make_document(db_session, org.id, name="one.pdf")
    await _make_document(db_session, org.id, name="two.pdf")
    await db_session.commit()

    rows = await execute_sql_query(db_session, "SELECT name FROM documents", org.id)
    assert len(rows) == 1


async def test_execute_sql_query_rejects_an_invalid_query(db_session):
    org = await _make_org(db_session, "SQL Invalid Org")
    with pytest.raises(SqlToolError):
        await execute_sql_query(db_session, "DROP TABLE documents", org.id)


# --------------------------------------- get_sql_schema / format_sql_results --


def test_get_sql_schema_returns_real_column_names():
    schema = get_sql_schema()
    assert "name" in schema["documents"]
    assert "organization_id" in schema["documents"]


def test_format_sql_results_renders_a_real_markdown_table():
    formatted = format_sql_results([{"name": "a.pdf"}, {"name": "b.pdf"}])
    assert "| name |" in formatted
    assert "a.pdf" in formatted


def test_format_sql_results_handles_empty_results():
    assert format_sql_results([]) == "No rows returned."
