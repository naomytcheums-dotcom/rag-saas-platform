"""Phase 4, Étape 2 correctif ciblé (2026-09-22) -- Partie B/F of the
targeted correction: real, deterministic citation validation, and its
own end-to-end traceability tests across every Advanced Retrieval
feature (Context Compression, Multi-Query, HyDE, MMR) plus Parent/Child
and multi-tenant isolation.

**Real, deliberate design confirmed by audit**: this codebase's own
`add_citations_to_response` (api/services/citations.py) never built a
`Citation` row from parsing `[N]` markers out of the LLM's own answer --
every real `Citation` was always built directly from the real,
ALREADY-RETRIEVED `chunks` list (`select_primary_sources(chunks, count)`).
There was never a route by which the LLM's own raw text could conjure a
fabricated citation. The real, genuine gap these tests close: nothing
previously checked whether a `[N]` marker the LLM actually WROTE
corresponds to one of the real, already-created `Citation` rows at all
-- `validate_citation_markers` (new) is that real, deterministic check,
never itself trusting the LLM's own claim."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.models.organization_settings import OrganizationSettings
from api.models.response import Response
from api.security.documents import generate_embeddings
from api.services.citations import (
    add_citations_to_response,
    extract_cited_numbers,
    get_citations_by_response,
    resolve_citation_source,
    validate_citation_markers,
)
from api.services.generation import generate_response
from api.services.retrieval_pipeline import search_with_context

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


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


def _fake_chunk(content, score=0.9):
    return {
        "chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": content, "score": score,
        "document_name": "d.pdf", "file_type": "pdf",
    }


# ==================================================================
# extract_cited_numbers / validate_citation_markers / resolve_citation_source
# ==================================================================


def test_extract_cited_numbers_finds_every_real_marker():
    """Test 19's own building block -- real, purely syntactic extraction."""
    assert extract_cited_numbers("Fact one [1]. Fact two [2]. Also [1] again.") == {1, 2}


def test_extract_cited_numbers_is_empty_for_no_real_markers():
    assert extract_cited_numbers("No markers here at all.") == set()
    assert extract_cited_numbers("") == set()


def test_extract_cited_numbers_is_none_safe():
    assert extract_cited_numbers(None) == set()


def test_validate_citation_markers_accepts_a_real_valid_citation():
    """Test 19 -- citation valide -> résolution vers le bon chunk."""
    response = Response(organization_id=uuid.uuid4(), query="q", answer="The answer is X [1].")
    citations = [_citation(citation_number=1)]
    result = validate_citation_markers(response, citations)
    assert result["valid_numbers"] == [1]
    assert result["invalid_numbers"] == []
    assert result["all_valid"] is True


def test_validate_citation_markers_rejects_a_nonexistent_citation():
    """Test 20 -- citation inexistante [999] -> rejetée."""
    response = Response(organization_id=uuid.uuid4(), query="q", answer="The answer is X [999].")
    citations = [_citation(citation_number=1), _citation(citation_number=2)]
    result = validate_citation_markers(response, citations)
    assert result["invalid_numbers"] == [999]
    assert result["all_valid"] is False


def test_validate_citation_markers_rejects_a_citation_outside_the_real_context():
    """Test 21 -- citation hors contexte: seuls [1]/[2] existent
    réellement, la réponse tente de citer [3]."""
    response = Response(organization_id=uuid.uuid4(), query="q", answer="Info X [1]. Info Y [2]. Info Z [3].")
    citations = [_citation(citation_number=1), _citation(citation_number=2)]
    result = validate_citation_markers(response, citations)
    assert result["valid_numbers"] == [1, 2]
    assert result["invalid_numbers"] == [3]
    assert result["all_valid"] is False


def test_validate_citation_markers_does_not_blindly_trust_the_llm():
    """Test 17's own explicit requirement -- a marker respecting the
    `[N]` syntax is never, on its own, treated as valid; only real,
    already-persisted Citation rows back a real marker."""
    response = Response(organization_id=uuid.uuid4(), query="q", answer="A fabricated source [42].")
    result = validate_citation_markers(response, citations=[])
    assert result["invalid_numbers"] == [42]
    assert result["valid_numbers"] == []


def test_validate_citation_markers_handles_a_real_response_with_no_citations():
    """Test 29 -- réponse sans citation -> comportement préservé."""
    response = Response(organization_id=uuid.uuid4(), query="q", answer="A plain answer with no markers.")
    result = validate_citation_markers(response, citations=[])
    assert result == {"cited_numbers": [], "valid_numbers": [], "invalid_numbers": [], "all_valid": True}


def test_validate_citation_markers_validates_every_citation_individually():
    """Test 30 -- plusieurs citations -> chacune validée individuellement."""
    response = Response(organization_id=uuid.uuid4(), query="q", answer="A [1]. B [2]. C [5].")
    citations = [_citation(citation_number=1), _citation(citation_number=2), _citation(citation_number=3)]
    result = validate_citation_markers(response, citations)
    assert result["cited_numbers"] == [1, 2, 5]
    assert result["valid_numbers"] == [1, 2]
    assert result["invalid_numbers"] == [5]


def test_validate_citation_markers_rejects_99_when_only_1_and_2_exist():
    """Mini-correctif final, Partie 5 -- exact literal scenario: only
    [1]/[2] are real citations, the LLM answer cites [99]."""
    response = Response(organization_id=uuid.uuid4(), query="q", answer="Fact A [1]. Fact B [2]. Fabricated [99].")
    citations = [_citation(citation_number=1), _citation(citation_number=2)]
    result = validate_citation_markers(response, citations)
    assert result["invalid_numbers"] == [99]
    assert result["valid_numbers"] == [1, 2]
    assert result["all_valid"] is False
    # Real, explicit check (requirement 18, "ne pas inventer une source") --
    # no 3rd real Citation row was ever fabricated to make [99] valid.
    assert len(citations) == 2


def test_validate_citation_markers_deduplicates_a_repeated_marker():
    """Mini-correctif final, Partie 5 -- `[1] ... [2] ... [1]`: a
    repeated real marker is reported once, not duplicated, and the
    real, underlying `Citation` rows are never touched or multiplied."""
    response = Response(organization_id=uuid.uuid4(), query="q", answer="Fact A [1]. Fact B [2]. Also fact A again [1].")
    citations = [_citation(citation_number=1), _citation(citation_number=2)]
    result = validate_citation_markers(response, citations)
    assert result["cited_numbers"] == [1, 2]  # [1] reported once, not twice
    assert result["valid_numbers"] == [1, 2]
    assert result["all_valid"] is True
    assert len(citations) == 2  # real citation rows untouched, never multiplied


def test_resolve_citation_source_reaches_the_real_document_and_chunk():
    """Test 22 -- citation valide -> résolution jusqu'au document/source
    réel, avec les identifiants réels."""
    chunk_id, document_id = uuid.uuid4(), uuid.uuid4()
    citation = _citation(citation_number=1, chunk_id=chunk_id, document_id=document_id, source_title="Handbook", document_name="handbook.pdf")
    resolved = resolve_citation_source(citation)
    assert resolved == {
        "chunk_id": chunk_id, "document_id": document_id, "source_title": "Handbook",
        "source_url": None, "document_name": "handbook.pdf",
    }


def _citation(citation_number, chunk_id=None, document_id=None, source_title=None, document_name=None):
    from api.models.citation import Citation

    return Citation(
        response_id=uuid.uuid4(), document_id=document_id or uuid.uuid4(), chunk_id=chunk_id or uuid.uuid4(),
        source_title=source_title, text="Some real cited text.", relevance_score=0.9,
        relevance_label="high", citation_number=citation_number, document_name=document_name, is_primary=True,
    )


# ==================================================================
# Real, end-to-end traceability (Test 19 continued / Tests 23-28)
# ==================================================================


async def test_chunk_to_citation_traceability_with_artificial_unique_chunks(monkeypatch, db_session):
    """Test 7 (Partie B) -- traçabilité chunk -> citation avec des
    chunks artificiels facilement reconnaissables: une question ciblant
    UNIQUE_A doit produire une citation reliée au Chunk A, jamais B/C."""
    monkeypatch.setattr(
        "api.services.generation.search_with_context",
        AsyncMock(return_value=[_fake_chunk("Chunk A carries information UNIQUE_A.", score=0.95)]),
    )
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("The answer is UNIQUE_A [1].")))

    org = await _make_org(db_session, "Org Traceability")
    await db_session.commit()
    response = await generate_response(db_session, org.id, "What is UNIQUE_A?")
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    assert len(citations) == 1
    assert "UNIQUE_A" in citations[0].text
    validation = validate_citation_markers(response, citations)
    assert validation["all_valid"] is True
    assert resolve_citation_source(citations[0])["chunk_id"] is not None


async def test_generate_response_llm_compression_citations_map_to_real_chunks(monkeypatch, db_session):
    """Test 23 -- Context Compression + citations: la compression ne
    doit jamais créer de nouvel identifiant de source (voir aussi
    tests/test_generation.py's own dedicated per-chunk mapping test) --
    ici on vérifie spécifiquement que `validate_citation_markers`
    accepte les marqueurs réels produits après compression."""
    chunk = _fake_chunk("The refund policy allows returns within 30 days.")
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=[chunk]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Refunds within 30 days [1].")))

    import api.services.context_compression as compression_module

    async def _fake_compress(chunks, max_tokens=None, method=None, query=None, **kwargs):
        return [{**c, "content": "COMPRESSED " + c["content"]} for c in chunks]

    monkeypatch.setattr(compression_module, "compress_context", _fake_compress)

    org = await _make_org(db_session, "Org Compression Citation Mapping")
    db_session.add(OrganizationSettings(organization_id=org.id, settings={"context_compression_enabled": True}))
    await db_session.commit()

    response = await generate_response(db_session, org.id, "refund policy")
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    validation = validate_citation_markers(response, citations)
    assert validation["all_valid"] is True
    assert "COMPRESSED" not in citations[0].text  # the real citation quotes the real, uncompressed chunk


async def test_multi_query_citations_only_reference_real_retrieved_chunks(monkeypatch, db_session):
    """Test 24 -- Multi-Query + citations: seuls les vrais chunks
    effectivement présents dans le résultat fusionné sont citables --
    les variantes de requête elles-mêmes ne sont jamais des sources."""
    mock_acompletion = AsyncMock(side_effect=[
        _real_response("How can I get a refund?\nWhat's the return policy?"),  # multi-query variants
        _real_response("Refunds are available within 30 days [1]."),  # final generation
    ])
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org Multi Query Citations")
    document = await _make_document(db_session, org.id)
    real_contents = ["The refund policy allows returns within 30 days of purchase.", "Our office relocated last year."]
    await _add_chunks(db_session, org.id, document.id, real_contents)
    db_session.add(OrganizationSettings(organization_id=org.id, settings={"multi_query_enabled": True, "multi_query_count": 2}))
    await db_session.commit()

    response = await generate_response(db_session, org.id, "refund policy")
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    assert len(citations) >= 1
    for citation in citations:
        assert citation.text in real_contents  # never a synthesized query variant
    validation = validate_citation_markers(response, citations)
    assert validation["all_valid"] is True


async def test_hyde_hypothetical_document_is_never_citable(monkeypatch, db_session):
    """Test 25 -- HyDE + citations: le document hypothétique HyDE n'est
    jamais une source citable, uniquement les chunks réellement
    récupérés."""
    hypothetical_text = "A vague hypothetical passage that was never actually stored anywhere."
    mock_acompletion = AsyncMock(side_effect=[
        _real_response(hypothetical_text),  # HyDE generation
        _real_response("Refunds are processed within 30 days [1]."),  # final generation
    ])
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org HyDE Citations")
    document = await _make_document(db_session, org.id)
    real_contents = ["Refunds are processed within 30 days of the original purchase."]
    await _add_chunks(db_session, org.id, document.id, real_contents)
    db_session.add(OrganizationSettings(organization_id=org.id, settings={"hyde_enabled": True}))
    await db_session.commit()

    response = await generate_response(db_session, org.id, "How do I get my money back?")
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    assert len(citations) >= 1
    for citation in citations:
        assert citation.text in real_contents
        assert citation.text != hypothetical_text
        assert hypothetical_text not in citation.text


async def test_mmr_eliminated_chunks_are_never_citable(db_session):
    """Test 26 -- MMR + citations: un chunk éliminé par MMR ne doit
    jamais pointer vers une citation."""
    org = await _make_org(db_session, "Org MMR Citations")
    document = await _make_document(db_session, org.id)
    texts = [
        "The refund policy allows returns within 30 days of purchase.",
        "Our refund policy permits returns within thirty days of buying.",
        "The office is located in downtown Paris.",
    ]
    await _add_chunks(db_session, org.id, document.id, texts)

    without_mmr = await search_with_context(db_session, org.id, "refund policy", strategy="vector_only", top_k=3, score_threshold=0.0)
    survivors = await search_with_context(
        db_session, org.id, "refund policy", strategy="vector_only", top_k=1, score_threshold=0.0,
        org_settings={"mmr_enabled": True, "mmr_lambda": 0.0},
    )
    eliminated_ids = {r["chunk_id"] for r in without_mmr} - {r["chunk_id"] for r in survivors}
    assert eliminated_ids  # a real, meaningful precondition: MMR really did eliminate at least one real candidate

    response = Response(organization_id=org.id, query="refund policy", answer="Refunds within 30 days [1].")
    db_session.add(response)
    await db_session.flush()
    citations = await add_citations_to_response(db_session, response, survivors, citation_count=5)
    await db_session.commit()

    cited_chunk_ids = {str(c.chunk_id) for c in citations}
    assert cited_chunk_ids.isdisjoint(eliminated_ids)  # never cites a chunk MMR discarded
    assert cited_chunk_ids == {r["chunk_id"] for r in survivors}


async def test_parent_child_citation_traceability_preserved(monkeypatch, db_session):
    """Test 27 -- Parent/Child + citations: une citation reste reliée au
    vrai chunk enfant réellement utilisé, jamais au parent."""
    org = await _make_org(db_session, "Org Parent Child Citations")
    document = await _make_document(db_session, org.id)
    parent = DocumentChunk(
        document_id=document.id, organization_id=org.id, chunk_role="parent",
        content="A much wider real parent paragraph about the refund policy and its exceptions.",
    )
    db_session.add(parent)
    await db_session.flush()

    child_text = "The refund policy allows returns within 30 days of purchase."
    embedding = generate_embeddings([child_text], EMBEDDING_MODEL)[0]
    child = DocumentChunk(
        document_id=document.id, organization_id=org.id, content=child_text, embedding=embedding,
        chunk_role="child", parent_chunk_id=parent.id,
        metadata_json={"parent_chunk_id": str(parent.id), "parent_context": parent.content},
    )
    db_session.add(child)
    await db_session.commit()

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Refunds within 30 days [1].")))
    response = await generate_response(db_session, org.id, "refund policy")
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    assert len(citations) == 1
    assert citations[0].chunk_id == child.id  # points at the real child, never the parent
    assert citations[0].chunk_id != parent.id  # mini-correctif final, Partie 5 -- explicit, direct exclusion check
    assert citations[0].text == child_text  # the child's own precise text, never the wider parent paragraph
    assert resolve_citation_source(citations[0])["chunk_id"] == child.id
    validation = validate_citation_markers(response, citations)
    assert validation["all_valid"] is True


async def test_citations_never_cross_tenant_boundaries(monkeypatch, db_session):
    """Test 28 -- Multi-tenant: une citation d'Organization A ne peut
    jamais se résoudre vers un document d'Organization B, même avec un
    contenu textuel identique."""
    org_a = await _make_org(db_session, "Org Tenant A")
    org_b = await _make_org(db_session, "Org Tenant B")
    doc_a = await _make_document(db_session, org_a.id, name="a.pdf")
    doc_b = await _make_document(db_session, org_b.id, name="b.pdf")
    identical_text = "The quarterly revenue report shows strong growth this year."
    await _add_chunks(db_session, org_a.id, doc_a.id, [identical_text])
    await _add_chunks(db_session, org_b.id, doc_b.id, [identical_text])

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Strong growth [1].")))
    response = await generate_response(db_session, org_a.id, "quarterly revenue")
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    assert len(citations) == 1
    resolved = resolve_citation_source(citations[0])
    assert resolved["document_id"] == doc_a.id
    assert resolved["document_id"] != doc_b.id
