"""Partie 5.4.4 -- RAG workflow block. `retrieval_pipeline.search` is
mocked at its own clean boundary (real, already covered end-to-end by
tests/test_retrieval_pipeline.py/test_search.py) -- this suite tests
the block's OWN real logic: validation, template rendering, metadata
filtering, and output formatting."""

import uuid
from unittest.mock import AsyncMock

import pytest

import api.services.workflow_block_rag as workflow_block_rag
from api.services.workflow_block_rag import (
    execute_rag_block, format_rag_results, render_rag_query, validate_rag_config,
)
from api.services.workflow_blocks import WorkflowBlockError


def _make_workspace(organization_id):
    from api.models.workspace import Workspace
    return Workspace(id=uuid.uuid4(), organization_id=organization_id, name="KB")


# --------------------------------------- validate_rag_config / render_rag_query / format_rag_results --


def test_validate_rag_config_accepts_a_real_valid_config():
    validate_rag_config({"query": "{{input}}", "top_k": 5, "strategy": "hybrid"})


def test_validate_rag_config_rejects_a_missing_query():
    """Validation criterion: la validation fonctionne."""
    with pytest.raises(WorkflowBlockError, match="query"):
        validate_rag_config({})


def test_validate_rag_config_rejects_a_non_positive_top_k():
    with pytest.raises(WorkflowBlockError):
        validate_rag_config({"query": "q", "top_k": 0})


def test_validate_rag_config_rejects_an_unknown_strategy():
    with pytest.raises(WorkflowBlockError, match="Unknown strategy"):
        validate_rag_config({"query": "q", "strategy": "not-real"})


def test_validate_rag_config_rejects_invalid_filters():
    with pytest.raises(WorkflowBlockError):
        validate_rag_config({"query": "q", "filters": {"not_a_real_field": "x"}})


def test_render_rag_query_substitutes_real_variables():
    """Validation criterion: le rendu des requêtes fonctionne."""
    assert render_rag_query("Find docs about {{topic}}", {"topic": "billing"}) == "Find docs about billing"


def test_format_rag_results_formats_real_results():
    """Validation criterion: les résultats sont formatés."""
    formatted = format_rag_results([{"document_name": "Doc A", "content": "hello"}])
    assert "Doc A" in formatted and "hello" in formatted


def test_format_rag_results_handles_no_results():
    assert format_rag_results([]) == "No relevant documents found."


# --------------------------------------- execute_rag_block --


async def test_execute_rag_block_returns_formatted_results_under_output_key(monkeypatch, db_session):
    """Validation criterion: l'exécution du bloc RAG fonctionne."""
    mock_search = AsyncMock(return_value=[{"document_name": "Doc A", "content": "hello world"}])
    monkeypatch.setattr(workflow_block_rag, "search", mock_search)

    org_id = uuid.uuid4()
    result = await execute_rag_block(db_session, org_id, {"query": "hi", "output_key": "docs"}, {})

    assert "Doc A" in result["docs"]
    mock_search.assert_called_once()


async def test_execute_rag_block_renders_real_query_variables(monkeypatch, db_session):
    mock_search = AsyncMock(return_value=[])
    monkeypatch.setattr(workflow_block_rag, "search", mock_search)

    await execute_rag_block(db_session, uuid.uuid4(), {"query": "about {{topic}}"}, {"topic": "invoices"})

    assert mock_search.call_args.args[2] == "about invoices"


async def test_execute_rag_block_applies_real_metadata_filters(monkeypatch, db_session):
    mock_search = AsyncMock(return_value=[
        {"document_name": "A", "content": "1", "document_type": "invoice"},
        {"document_name": "B", "content": "2", "document_type": "contract"},
    ])
    monkeypatch.setattr(workflow_block_rag, "search", mock_search)

    result = await execute_rag_block(db_session, uuid.uuid4(), {"query": "hi", "filters": {"document_type": "invoice"}}, {})

    assert "A" in result["output"]
    assert "B" not in result["output"]


async def test_execute_rag_block_validates_a_real_knowledge_base_in_the_same_org(db_session):
    """Validation criterion: sécurité -- rejet inter-organisation."""
    other_workspace = _make_workspace(uuid.uuid4())
    db_session.add(other_workspace)
    await db_session.commit()

    with pytest.raises(WorkflowBlockError):
        await execute_rag_block(db_session, uuid.uuid4(), {"query": "hi", "knowledge_base_id": other_workspace.id}, {})


async def test_execute_rag_block_raises_on_invalid_config():
    """Validation criterion: robustesse -- que se passe-t-il si la KB est vide/mal configurée."""
    with pytest.raises(WorkflowBlockError):
        await execute_rag_block(None, uuid.uuid4(), {}, {})
