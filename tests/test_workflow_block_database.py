"""Partie 5.4.12 -- Database workflow block. Real SQLite execution
(no mocking), same precedent as tests/test_sql_tool.py."""

import uuid

import pytest

from api.models.document import Document, DocumentStatus
from api.models.organization import Organization
from api.services.workflow_block_database import (
    execute_database_block, format_database_results, render_sql_query, validate_sql_query,
)
from api.services.workflow_blocks import WorkflowBlockError


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


# --------------------------------------- validate_sql_query / render_sql_query / format_database_results --


def test_validate_sql_query_accepts_a_real_valid_select():
    """Validation criterion: la validation fonctionne."""
    validate_sql_query("SELECT name FROM documents")


def test_validate_sql_query_rejects_a_real_write_statement():
    """Validation criterion: sécurité -- protection contre les injections/écritures."""
    with pytest.raises(WorkflowBlockError, match="read-only SELECT"):
        validate_sql_query("DELETE FROM documents")


def test_validate_sql_query_rejects_a_join():
    with pytest.raises(WorkflowBlockError):
        validate_sql_query("SELECT * FROM documents JOIN conversations ON 1=1")


def test_render_sql_query_substitutes_real_variables():
    """Validation criterion: le rendu des requêtes fonctionne."""
    assert render_sql_query("SELECT * FROM {{table}}", {"table": "documents"}) == "SELECT * FROM documents"


def test_format_database_results_wraps_rows_and_a_real_markdown_table():
    formatted = format_database_results([{"name": "a.pdf"}])
    assert formatted["rows"] == [{"name": "a.pdf"}]
    assert "a.pdf" in formatted["formatted"]


# --------------------------------------- execute_database_block --


async def test_execute_database_block_returns_real_rows(db_session):
    """Validation criterion: l'exécution du bloc Database fonctionne."""
    org = await _make_org(db_session, "Workflow DB Org")
    await _make_document(db_session, org.id, name="alpha.pdf")
    await db_session.commit()

    result = await execute_database_block(
        db_session, org.id, {"query": "SELECT name FROM documents", "output_key": "docs"}, {},
    )
    assert result["docs"]["rows"] == [{"name": "alpha.pdf"}]


async def test_execute_database_block_renders_real_query_variables(db_session):
    org = await _make_org(db_session, "Workflow DB Org 2")
    await _make_document(db_session, org.id, name="beta.pdf")
    await db_session.commit()

    result = await execute_database_block(db_session, org.id, {"query": "SELECT name FROM {{table}}"}, {"table": "documents"})
    assert result["output"]["rows"] == [{"name": "beta.pdf"}]


async def test_execute_database_block_never_returns_another_organizations_rows(db_session):
    """Validation criterion: sécurité -- isolation multi-tenant réelle."""
    org_a = await _make_org(db_session, "DB Org A")
    org_b = await _make_org(db_session, "DB Org B")
    await _make_document(db_session, org_a.id, name="a-doc.pdf")
    await _make_document(db_session, org_b.id, name="b-doc.pdf")
    await db_session.commit()

    result = await execute_database_block(db_session, org_a.id, {"query": "SELECT name FROM documents"}, {})
    assert result["output"]["rows"] == [{"name": "a-doc.pdf"}]


async def test_execute_database_block_respects_real_max_rows(db_session, monkeypatch):
    from api.config import settings
    monkeypatch.setattr(settings, "SQL_TOOL_MAX_ROWS", 100)
    org = await _make_org(db_session, "DB Max Rows Org")
    await _make_document(db_session, org.id, name="a.pdf")
    await _make_document(db_session, org.id, name="b.pdf")
    await db_session.commit()

    result = await execute_database_block(db_session, org.id, {"query": "SELECT name FROM documents", "max_rows": 1}, {})
    assert len(result["output"]["rows"]) == 1


async def test_execute_database_block_rejects_a_missing_query(db_session):
    """Validation criterion: robustesse -- les erreurs sont gérées."""
    with pytest.raises(WorkflowBlockError, match="query"):
        await execute_database_block(db_session, uuid.uuid4(), {}, {})


async def test_execute_database_block_rejects_read_only_false(db_session):
    with pytest.raises(WorkflowBlockError, match="read_only"):
        await execute_database_block(db_session, uuid.uuid4(), {"query": "SELECT 1", "read_only": False}, {})


async def test_execute_database_block_rejects_a_custom_connection(db_session):
    with pytest.raises(WorkflowBlockError, match="connection"):
        await execute_database_block(db_session, uuid.uuid4(), {"query": "SELECT 1", "connection": "custom"}, {})


async def test_execute_database_block_rejects_an_invalid_query(db_session):
    org = await _make_org(db_session, "DB Invalid Query Org")
    await db_session.commit()
    with pytest.raises(WorkflowBlockError):
        await execute_database_block(db_session, org.id, {"query": "DROP TABLE documents"}, {})
