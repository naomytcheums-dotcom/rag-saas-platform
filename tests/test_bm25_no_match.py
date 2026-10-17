"""bm25_search returns only chunks that share at least one term with the query (found by scripts/e2e_rag_ingestion_search.py on a real stack: a query with no
matching term came back with a score-0.0 candidate, and in a one-document corpus a real match scored negative and ranked behind a non-match)."""

import uuid

from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.security.documents import generate_embeddings
from api.services.retrieval_pipeline import bm25_search, hybrid_search

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


async def _org_with_chunks(db_session, texts):
    org = Organization(name="Bm25 Org", slug=f"bm25-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    document = Document(
        organization_id=org.id, name="doc.txt", file_key=f"documents/{uuid.uuid4()}/doc.txt", file_size=10, file_type="text/plain", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    for text, embedding in zip(texts, generate_embeddings(texts, EMBEDDING_MODEL)):
        db_session.add(DocumentChunk(document_id=document.id, organization_id=org.id, content=text, embedding=embedding))
    await db_session.commit()
    return org


async def test_a_query_with_no_matching_term_has_no_real_match(db_session):
    org = await _org_with_chunks(db_session, ["The kiln fires at 1180 degrees.", "Refunds are possible within 14 days."])

    results = await bm25_search(db_session, org.id, "xyzzyplugh qwertyuiop", top_k=5)

    assert all(r["score"] <= 0.0 for r in results), "nothing may look like a lexical match when no term is shared"


async def test_the_chunk_sharing_a_term_ranks_first(db_session):
    org = await _org_with_chunks(db_session, ["The kiln fires at 1180 degrees.", "Refunds are possible within 14 days.", "Unrelated sentence about tea."])

    results = await bm25_search(db_session, org.id, "kiln degrees", top_k=5)

    assert results[0]["content"] == "The kiln fires at 1180 degrees."


async def test_a_match_is_returned_even_when_the_corpus_is_one_chunk(db_session):
    org = await _org_with_chunks(db_session, ["Zorblax support opens at nine."])

    results = await bm25_search(db_session, org.id, "zorblax support line", top_k=5)

    assert len(results) == 1 and "Zorblax" in results[0]["content"]


async def test_hybrid_still_returns_vector_candidates_for_a_query_without_lexical_match(db_session):
    org = await _org_with_chunks(db_session, ["The kiln fires at 1180 degrees.", "Refunds are possible within 14 days."])

    results = await hybrid_search(db_session, org.id, "how hot does the oven get", top_k=5)

    assert results, "the vector leg must still answer a paraphrase with no shared word"
