"""Partie 5.2.1 -- Search Knowledge Base tool. Real embeddings, real
search pipeline underneath -- no mocking, same precedent as
tests/test_retrieval_pipeline.py."""

import uuid

from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.security.documents import generate_embeddings
from api.tools.search_kb import (
    get_knowledge_base_stats, make_search_kb_tool, search_knowledge_base, search_knowledge_base_by_metadata,
    search_knowledge_base_with_rerank,
)

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


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


async def _add_chunks(db_session, org_id, document_id, texts):
    embeddings = generate_embeddings(texts, EMBEDDING_MODEL)
    for text, embedding in zip(texts, embeddings):
        db_session.add(DocumentChunk(document_id=document_id, organization_id=org_id, content=text, embedding=embedding))
    await db_session.commit()


async def test_search_knowledge_base_finds_real_relevant_chunks(db_session):
    """Validation criterion: la recherche dans la KB fonctionne."""
    org = await _make_org(db_session, "KB Tool Org")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["The cat sat on the mat.", "Quarterly revenue grew 12 percent."])

    results = await search_knowledge_base(db_session, org.id, "financial revenue growth")
    assert any("revenue" in r["content"] for r in results)


async def test_search_knowledge_base_never_returns_another_organizations_chunks(db_session):
    """Validation criterion: sécurité -- la recherche est limitée à
    l'organisation de l'utilisateur."""
    org_a = await _make_org(db_session, "KB Org A")
    org_b = await _make_org(db_session, "KB Org B")
    doc_a = await _make_document(db_session, org_a.id)
    doc_b = await _make_document(db_session, org_b.id)
    await _add_chunks(db_session, org_a.id, doc_a.id, ["Org A secret roadmap details."])
    await _add_chunks(db_session, org_b.id, doc_b.id, ["Org B secret roadmap details."])

    results = await search_knowledge_base(db_session, org_a.id, "roadmap")
    assert all("Org A" in r["content"] for r in results)


async def test_search_knowledge_base_with_rerank_returns_real_results(db_session):
    """Validation criterion: le reranking fonctionne."""
    org = await _make_org(db_session, "KB Rerank Org")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["Python is a programming language.", "Bananas are yellow fruit."])

    results = await search_knowledge_base_with_rerank(db_session, org.id, "programming languages")
    assert len(results) > 0
    assert "score" in results[0]


async def test_search_knowledge_base_by_metadata_filters_correctly(db_session):
    """Validation criterion: les filtres fonctionnent."""
    org = await _make_org(db_session, "KB Metadata Org")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["chunk one", "chunk two"])

    results = await search_knowledge_base_by_metadata(db_session, org.id, {})
    assert len(results) == 2


async def test_get_knowledge_base_stats_returns_real_counts(db_session):
    org = await _make_org(db_session, "KB Stats Org")
    stats = await get_knowledge_base_stats(db_session, org.id)
    assert "documents" in stats
    assert "kb_size_mb" in stats


async def test_make_search_kb_tool_handler_formats_real_results(db_session):
    org = await _make_org(db_session, "KB Handler Org")
    document = await _make_document(db_session, org.id, name="report.pdf")
    await _add_chunks(db_session, org.id, document.id, ["The annual report shows strong growth."])

    tool = make_search_kb_tool(db_session, org.id)
    result = await tool.handler(query="annual report growth")
    assert "report.pdf" in result


async def test_make_search_kb_tool_handler_handles_no_results(db_session):
    org = await _make_org(db_session, "KB Empty Org")
    tool = make_search_kb_tool(db_session, org.id)
    result = await tool.handler(query="anything")
    assert "No relevant documents" in result
