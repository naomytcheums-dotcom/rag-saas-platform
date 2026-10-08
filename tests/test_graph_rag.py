"""
api/services/graph_rag.py -- LightRAG's own real entity/relation
extraction makes real LLM calls with its own internal prompt/parsing
contract this test suite cannot honestly reproduce with a naive mock
(unlike litellm.acompletion, whose real RESPONSE SHAPE is documented
and mockable -- see tests/test_llm_providers.py's own docstring).
Tests here prove the real, verifiable part: this module's adapters
call THIS codebase's own real chat_completion/generate_embeddings
(never a second, independent LLM/embedding path), with the real
shapes those functions expect. A full ainsert()/aquery() round trip
needs a real, live LLM key and is intentionally not run here -- see
ROADMAP.md's own entry for how to run it manually once a key is
available (same "don't fake a live LLM run" discipline as
tests/test_llm_providers.py itself).
"""

import uuid
from unittest.mock import AsyncMock

import numpy as np
import pytest

import api.services.graph_rag as graph_rag
from api.services.graph_rag import _llm_model_func, _make_embedding_func, get_lightrag


async def test_llm_model_func_adapts_to_the_real_chat_completion(monkeypatch):
    """Validation criterion: a graph query must bill the SAME
    organization-configured provider every other real LLM call in this
    codebase uses -- never LightRAG's own independent default."""
    mock_chat_completion = AsyncMock(return_value="real extracted entities")
    monkeypatch.setattr("api.services.llm_providers.chat_completion", mock_chat_completion)

    result = await _llm_model_func("Extract entities from this text.", system_prompt="You are an extractor.")

    assert result == "real extracted entities"
    messages = mock_chat_completion.call_args.args[0]
    assert messages[-1] == {"role": "user", "content": "Extract entities from this text."}
    assert {"role": "system", "content": "You are an extractor."} in messages


async def test_embedding_func_calls_the_real_local_embedder():
    """Real, no mock needed -- generate_embeddings is local
    sentence-transformers, the exact same path the main ingestion
    pipeline already uses, not a second, parallel embedding path."""
    embed = _make_embedding_func("sentence-transformers/all-MiniLM-L6-v2")

    result = await embed(["hello world", "second real sentence"])

    assert isinstance(result, np.ndarray)
    assert result.shape[0] == 2
    assert result.shape[1] == 384  # real, known dimension of this real, local model


async def test_get_lightrag_builds_a_real_per_organization_instance(monkeypatch, tmp_path):
    """Validation criterion: real per-organization isolation -- two
    different organizations never share a working_dir."""
    monkeypatch.setattr("api.services.graph_rag._STORAGE_ROOT", tmp_path)
    org_a, org_b = uuid.uuid4(), uuid.uuid4()

    rag_a = await get_lightrag(org_a, "sentence-transformers/all-MiniLM-L6-v2")
    rag_b = await get_lightrag(org_b, "sentence-transformers/all-MiniLM-L6-v2")

    assert rag_a is not rag_b
    assert str(org_a) in rag_a.working_dir
    assert str(org_b) in rag_b.working_dir
    # Real, cached instance -- calling again for the same org returns
    # the SAME object, not a freshly-rebuilt one.
    assert await get_lightrag(org_a, "sentence-transformers/all-MiniLM-L6-v2") is rag_a


async def test_ingest_into_graph_tags_real_inserts_with_the_real_document_id(monkeypatch):
    """Hardening Mission, Phase 6 -- REGRESSION for a real, confirmed
    audit gap: this module used to insert anonymous text with no way to
    ever selectively remove it again. `ids=` (LightRAG's own real,
    verified `ainsert` parameter) must carry the real document_id."""
    fake_rag = type("FakeRag", (), {"ainsert": AsyncMock()})()
    monkeypatch.setattr(graph_rag, "get_lightrag", AsyncMock(return_value=fake_rag))
    document_id = uuid.uuid4()

    await graph_rag.ingest_into_graph(uuid.uuid4(), ["chunk one", "chunk two"], "sentence-transformers/all-MiniLM-L6-v2", document_id=document_id)

    assert fake_rag.ainsert.await_count == 2
    for call in fake_rag.ainsert.await_args_list:
        assert call.kwargs["ids"] == str(document_id)


async def test_ingest_into_graph_without_a_document_id_stays_byte_identical(monkeypatch):
    """Real backward compatibility: every pre-existing real caller that
    never passes document_id must keep inserting with `ids=None`."""
    fake_rag = type("FakeRag", (), {"ainsert": AsyncMock()})()
    monkeypatch.setattr(graph_rag, "get_lightrag", AsyncMock(return_value=fake_rag))

    await graph_rag.ingest_into_graph(uuid.uuid4(), ["chunk"], "sentence-transformers/all-MiniLM-L6-v2")

    assert fake_rag.ainsert.await_args.kwargs["ids"] is None


async def test_delete_document_from_graph_calls_the_real_lightrag_delete_by_doc_id(monkeypatch):
    """Hardening Mission, Phase 6 -- REGRESSION: a confirmed GDPR gap
    (no way to selectively remove one document's own real contribution
    to a shared organization graph) is now closed via LightRAG's own
    real `adelete_by_doc_id` (verified directly against the installed
    package before writing this)."""
    fake_rag = type("FakeRag", (), {"adelete_by_doc_id": AsyncMock()})()
    monkeypatch.setattr(graph_rag, "get_lightrag", AsyncMock(return_value=fake_rag))
    document_id = uuid.uuid4()

    await graph_rag.delete_document_from_graph(uuid.uuid4(), document_id, "sentence-transformers/all-MiniLM-L6-v2")

    fake_rag.adelete_by_doc_id.assert_awaited_once_with(str(document_id))


async def test_purge_organization_graph_removes_the_real_working_directory_and_evicts_the_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(graph_rag, "_STORAGE_ROOT", tmp_path)
    org_id = uuid.uuid4()
    working_dir = tmp_path / str(org_id)
    working_dir.mkdir(parents=True)
    (working_dir / "kv_store.json").write_text("{}")
    graph_rag._INSTANCES[org_id] = object()

    await graph_rag.purge_organization_graph(org_id)

    assert not working_dir.exists()
    assert org_id not in graph_rag._INSTANCES


async def test_purge_organization_graph_is_a_real_no_op_for_an_org_with_no_graph(tmp_path, monkeypatch):
    monkeypatch.setattr(graph_rag, "_STORAGE_ROOT", tmp_path)
    await graph_rag.purge_organization_graph(uuid.uuid4())  # must not raise
