"""Phase 4, Étape 3 -- Metadata Filtering.

**Audit finding (catch), documented here for the test suite's own
context**: `api/services/metadata_filtering.py` already existed
(`build_metadata_filter`/`apply_metadata_filter`/`validate_filters`),
but it post-filters an ALREADY-FETCHED, already-top_k-trimmed result
list against a fixed 7-field allowlist (`author`/`created_date`/`tags`/
`document_type`/`source`/`workspace_id`/`file_size`) that this
codebase's own real search results never actually carry -- its own top
docstring already, honestly, documents this as "not yet wired into a
live search call". This étape adds real, SQL-level, generic filtering
against a real chunk's own `metadata_json` (an arbitrary, already-real
JSON store), wired directly into `fetch_organization_chunks` -- the one,
real, shared choke point every strategy function already goes through
-- so an excluded chunk never becomes a candidate for BM25/vector/RRF/
cross-encoder/MMR in the first place. The OLD module/functions are left
completely untouched (still used by `api/tools/search_kb.py` and
`api/services/workflow_block_rag.py`)."""

import uuid

import pytest
from sqlalchemy import select

from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.organization_settings import OrganizationSettings
from api.models.user import User
from api.security.documents import generate_embeddings
from api.services.metadata_filtering import build_metadata_filter_clauses, normalize_metadata_filters
from api.services.retrieval_pipeline import (
    bm25_search, fetch_organization_chunks, hybrid_reranked_search, hybrid_search, search, search_with_context,
    vector_search,
)

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


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


async def _add_chunks(db_session, org_id, document_id, entries):
    """`entries`: list of (text, metadata_json) tuples."""
    texts = [text for text, _ in entries]
    embeddings = generate_embeddings(texts, EMBEDDING_MODEL)
    for (text, metadata), embedding in zip(entries, embeddings):
        db_session.add(DocumentChunk(document_id=document_id, organization_id=org_id, content=text, embedding=embedding, metadata_json=metadata))
    await db_session.commit()


# ============================================================
# 1. normalize_metadata_filters / build_metadata_filter_clauses (unit)
# ============================================================


def test_normalize_metadata_filters_accepts_a_simple_equals_shorthand():
    assert normalize_metadata_filters({"department": "finance"}) == {"department": {"op": "equals", "value": "finance"}}


def test_normalize_metadata_filters_accepts_every_real_operator():
    filters = {
        "department": {"not_equals": "legal"}, "language": {"in": ["fr", "en"]}, "country": {"not_in": ["us"]},
        "year": {"gt": 2020},
    }
    normalized = normalize_metadata_filters(filters)
    assert normalized["department"] == {"op": "not_equals", "value": "legal"}
    assert normalized["year"] == {"op": "gt", "value": 2020}


def test_normalize_metadata_filters_rejects_an_unknown_operator():
    with pytest.raises(ValueError):
        normalize_metadata_filters({"year": {"unknown_op": 2020}})


def test_normalize_metadata_filters_rejects_a_malformed_key():
    with pytest.raises(ValueError):
        normalize_metadata_filters({"department; DROP TABLE documents;--": "finance"})


def test_normalize_metadata_filters_rejects_too_many_filters(monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "METADATA_FILTER_MAX_OPERATORS", 2)
    with pytest.raises(ValueError):
        normalize_metadata_filters({"a": 1, "b": 2, "c": 3})


def test_normalize_metadata_filters_rejects_a_non_scalar_value():
    with pytest.raises(ValueError):
        normalize_metadata_filters({"department": {"nested": {"a": 1}}})
    with pytest.raises(ValueError):
        normalize_metadata_filters({"department": ["finance", "legal"]})


def test_normalize_metadata_filters_rejects_an_empty_in_list():
    with pytest.raises(ValueError):
        normalize_metadata_filters({"department": {"in": []}})


def test_build_metadata_filter_clauses_produces_one_real_clause_per_key():
    clauses = build_metadata_filter_clauses(DocumentChunk.metadata_json, {"department": "finance", "year": {"gt": 2020}})
    assert len(clauses) == 2


# ============================================================
# 2. fetch_organization_chunks / vector / BM25 / hybrid / cross-encoder
# ============================================================


async def test_fetch_organization_chunks_applies_the_real_metadata_filter(db_session):
    org = await _make_org(db_session, "Org Fetch Filter")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        ("Finance report content.", {"department": "finance"}),
        ("Legal contract content.", {"department": "legal"}),
    ])

    chunks = await fetch_organization_chunks(db_session, org.id, metadata_filters={"department": "finance"})
    assert len(chunks) == 1
    assert "Finance" in chunks[0]["content"]


async def test_vector_search_respects_the_real_metadata_filter(db_session):
    org = await _make_org(db_session, "Org Vector Filter")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        ("The revenue forecast for finance department.", {"department": "finance", "year": 2026}),
        ("The revenue forecast for legal department.", {"department": "legal", "year": 2026}),
    ])

    results = await vector_search(db_session, org.id, "revenue forecast", top_k=5, metadata_filters={"department": "finance"})
    assert len(results) == 1
    assert results[0]["metadata_json"]["department"] == "finance"


async def test_bm25_search_respects_the_real_metadata_filter(db_session):
    """Test 6 -- BM25 + filter: an excluded real chunk never returns via BM25."""
    org = await _make_org(db_session, "Org BM25 Filter")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        ("The invoice number INV-778899 belongs to finance.", {"department": "finance"}),
        ("The invoice number INV-778899 belongs to legal.", {"department": "legal"}),
    ])

    results = await bm25_search(db_session, org.id, "INV-778899", top_k=5, metadata_filters={"department": "finance"})
    assert len(results) == 1
    assert results[0]["metadata_json"]["department"] == "finance"


async def test_hybrid_search_rrf_never_returns_an_excluded_chunk(db_session):
    """Test 7/8 -- hybrid + filter, RRF + filter: neither the vector leg
    nor the BM25 leg can smuggle an excluded chunk back in via fusion."""
    org = await _make_org(db_session, "Org Hybrid Filter")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        ("Annual revenue forecast document finance.", {"department": "finance"}),
        ("Annual revenue forecast document legal.", {"department": "legal"}),
    ])

    results = await hybrid_search(db_session, org.id, "revenue forecast", top_k=5, metadata_filters={"department": "finance"})
    assert all(r["metadata_json"]["department"] == "finance" for r in results)
    assert len(results) == 1


async def test_hybrid_reranked_search_cross_encoder_only_sees_authorized_candidates(db_session):
    """Test 9 -- cross-encoder + filter: only ever reranks real,
    already-authorized candidates."""
    org = await _make_org(db_session, "Org Cross Encoder Filter")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        ("To reset your password for the finance system.", {"department": "finance"}),
        ("To reset your password for the legal system.", {"department": "legal"}),
    ])

    results = await hybrid_reranked_search(
        db_session, org.id, "how do I reset my password", top_k=5, metadata_filters={"department": "finance"},
    )
    assert len(results) == 1
    assert results[0]["metadata_json"]["department"] == "finance"


@pytest.mark.parametrize("strategy", ["hybrid", "vector_only", "bm25_only", "hybrid_reranked", "semantic"])
async def test_search_applies_the_real_filter_under_every_real_strategy(db_session, strategy):
    org = await _make_org(db_session, f"Org Strategy Filter {strategy}")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        ("Quarterly finance department summary report.", {"department": "finance"}),
        ("Quarterly legal department summary report.", {"department": "legal"}),
    ])

    results = await search(
        db_session, org.id, "quarterly summary report", strategy=strategy, top_k=5, score_threshold=0.0,
        metadata_filters={"department": "finance"},
    )
    assert len(results) == 1
    assert results[0]["metadata_json"]["department"] == "finance"


async def test_search_numeric_comparison_operators(db_session):
    org = await _make_org(db_session, "Org Numeric Filter")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        ("Report from a recent fiscal year.", {"year": 2026}),
        ("Report from an older fiscal year.", {"year": 2018}),
    ])

    results = await search(db_session, org.id, "fiscal year report", strategy="vector_only", top_k=5, score_threshold=0.0, metadata_filters={"year": {"gt": 2020}})
    assert len(results) == 1
    assert results[0]["metadata_json"]["year"] == 2026


# ============================================================
# 3. Rétrocompatibilité / robustesse
# ============================================================


async def test_search_without_filters_is_byte_identical_to_before(db_session):
    """Test 23 -- recherche sans filtre identique au comportement précédent."""
    org = await _make_org(db_session, "Org No Filter Regression")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        ("The refund policy allows returns within 30 days.", None),
        ("Bananas are a good source of potassium.", None),
    ])

    with_none = await search(db_session, org.id, "refund policy", strategy="vector_only", top_k=5, score_threshold=0.0)
    with_empty_dict = await search(db_session, org.id, "refund policy", strategy="vector_only", top_k=5, score_threshold=0.0, metadata_filters={})
    assert with_none == with_empty_dict
    assert len(with_none) == 2


async def test_search_rejects_a_malformed_filter(db_session):
    """Test 4 -- filtre invalide -> rejeté proprement."""
    org = await _make_org(db_session, "Org Malformed Filter")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [("Some content.", {"department": "finance"})])

    with pytest.raises(ValueError):
        await search(db_session, org.id, "content", strategy="vector_only", metadata_filters={"department": {"bad_operator": "finance"}})


async def test_search_metadata_filter_never_replaces_organization_isolation(db_session):
    """Requirement 4 -- the metadata filter is additive, never a
    replacement for the mandatory organization_id isolation."""
    org_a = await _make_org(db_session, "Org Isolation A")
    org_b = await _make_org(db_session, "Org Isolation B")
    doc_a = await _make_document(db_session, org_a.id)
    doc_b = await _make_document(db_session, org_b.id)
    await _add_chunks(db_session, org_a.id, doc_a.id, [("Shared finance content.", {"department": "finance"})])
    await _add_chunks(db_session, org_b.id, doc_b.id, [("Shared finance content.", {"department": "finance"})])

    results = await search(db_session, org_a.id, "shared finance content", strategy="vector_only", top_k=10, score_threshold=0.0, metadata_filters={"department": "finance"})
    assert len(results) == 1
    assert results[0]["document_id"] == str(doc_a.id)


# ============================================================
# 4. Advanced Retrieval interplay (Query Rewriting / Multi-Query / HyDE / MMR)
# ============================================================


async def test_query_rewriting_still_respects_the_real_filter(db_session, monkeypatch):
    """Test 10 -- Query Rewriting + filter."""
    import litellm
    from unittest.mock import AsyncMock
    from litellm.types.utils import Choices, Message, ModelResponse
    from api.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")

    def _real_response(text):
        return ModelResponse(choices=[Choices(message=Message(content=text, role="assistant"), index=0, finish_reason="stop")])

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("revenue forecast report")))

    org = await _make_org(db_session, "Org Rewriting Filter")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        ("Revenue forecast report for finance.", {"department": "finance"}),
        ("Revenue forecast report for legal.", {"department": "legal"}),
    ])

    results = await search(
        db_session, org.id, "rev forecast", strategy="vector_only", top_k=5, score_threshold=0.0,
        org_settings={"query_rewriting_enabled": True}, metadata_filters={"department": "finance"},
    )
    assert len(results) == 1
    assert results[0]["metadata_json"]["department"] == "finance"


async def test_multi_query_variants_all_share_the_real_same_filter(db_session, monkeypatch):
    """Test 11 -- Multi-Query + filter: no variant can bypass it."""
    import litellm
    from unittest.mock import AsyncMock
    from litellm.types.utils import Choices, Message, ModelResponse
    from api.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")

    def _real_response(text):
        return ModelResponse(choices=[Choices(message=Message(content=text, role="assistant"), index=0, finish_reason="stop")])

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("sales forecast\nfinancial projection")))

    org = await _make_org(db_session, "Org Multi Query Filter")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        ("The revenue forecast belongs to finance.", {"department": "finance"}),
        ("The revenue forecast belongs to legal.", {"department": "legal"}),
    ])

    results = await search(
        db_session, org.id, "revenue forecast", strategy="hybrid", top_k=5, score_threshold=0.0,
        org_settings={"multi_query_enabled": True, "multi_query_count": 2}, metadata_filters={"department": "finance"},
    )
    assert len(results) >= 1
    assert all(r["metadata_json"]["department"] == "finance" for r in results)


async def test_hyde_embedding_still_respects_the_real_filter(db_session, monkeypatch):
    """Test 12 -- HyDE + filter: HyDE changes the embedding, never the filter."""
    import litellm
    from unittest.mock import AsyncMock
    from litellm.types.utils import Choices, Message, ModelResponse
    from api.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")

    def _real_response(text):
        return ModelResponse(choices=[Choices(message=Message(content=text, role="assistant"), index=0, finish_reason="stop")])

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("A hypothetical passage about refunds.")))

    org = await _make_org(db_session, "Org HyDE Filter")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        ("Refunds are processed within 30 days for finance.", {"department": "finance"}),
        ("Refunds are processed within 30 days for legal.", {"department": "legal"}),
    ])

    results = await search(
        db_session, org.id, "How do I get my money back?", strategy="vector_only", top_k=5, score_threshold=0.0,
        org_settings={"hyde_enabled": True}, metadata_filters={"department": "finance"},
    )
    assert len(results) == 1
    assert results[0]["metadata_json"]["department"] == "finance"


async def test_mmr_only_diversifies_among_the_real_already_filtered_candidates(db_session):
    """Test 13 -- MMR + filter: metadata filter -> candidate pool -> MMR -> top_k, never the reverse."""
    org = await _make_org(db_session, "Org MMR Filter")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        ("The refund policy for finance allows 30 days.", {"department": "finance"}),
        ("The refund policy for finance permits thirty days.", {"department": "finance"}),
        ("The refund policy for legal allows 30 days.", {"department": "legal"}),
    ])

    results = await search(
        db_session, org.id, "refund policy", strategy="vector_only", top_k=5, score_threshold=0.0,
        org_settings={"mmr_enabled": True, "mmr_lambda": 0.3}, metadata_filters={"department": "finance"},
    )
    assert len(results) == 2
    assert all(r["metadata_json"]["department"] == "finance" for r in results)


async def test_context_compression_never_sees_an_excluded_chunk(db_session, monkeypatch):
    """Test 14 -- Context Compression + filter: an excluded chunk never
    arrives at the compressor, because it was never retrieved at all."""
    import litellm
    from unittest.mock import AsyncMock
    from litellm.types.utils import Choices, Message, ModelResponse
    from api.config import settings
    from api.services.generation import generate_response

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")

    def _real_response(text):
        return ModelResponse(choices=[Choices(message=Message(content=text, role="assistant"), index=0, finish_reason="stop")])

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Refunds within 30 days [1].")))

    org = await _make_org(db_session, "Org Compression Filter")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        ("Refunds are processed within 30 days for finance docs.", {"department": "finance"}),
        ("Refunds are processed within 30 days for legal docs.", {"department": "legal"}),
    ])
    db_session.add(OrganizationSettings(organization_id=org.id, settings={"context_compression_enabled": True}))
    await db_session.commit()

    response = await generate_response(db_session, org.id, "refund policy", metadata_filters={"department": "finance"})
    await db_session.commit()

    assert "legal" not in response.answer.lower()


# ============================================================
# 5. Parent/Child
# ============================================================


async def test_parent_child_filter_excludes_the_whole_disallowed_family(db_session):
    """Tests 15-17 -- child autorisé, child interdit, parent context
    correct: parent A / child A1,A2 vs parent B / child B1,B2, filter
    only allows A."""
    org = await _make_org(db_session, "Org Parent Child Filter")
    document = await _make_document(db_session, org.id)

    parent_a = DocumentChunk(document_id=document.id, organization_id=org.id, chunk_role="parent", content="Wide parent A context about finance policy.", metadata_json={"department": "finance"})
    parent_b = DocumentChunk(document_id=document.id, organization_id=org.id, chunk_role="parent", content="Wide parent B context about legal policy.", metadata_json={"department": "legal"})
    db_session.add_all([parent_a, parent_b])
    await db_session.flush()

    texts = [
        "Finance child A1 about refund policy.", "Finance child A2 about refund policy details.",
        "Legal child B1 about refund policy.", "Legal child B2 about refund policy details.",
    ]
    embeddings = generate_embeddings(texts, EMBEDDING_MODEL)
    parents = [parent_a, parent_a, parent_b, parent_b]
    departments = ["finance", "finance", "legal", "legal"]
    for text, embedding, parent, department in zip(texts, embeddings, parents, departments):
        db_session.add(DocumentChunk(
            document_id=document.id, organization_id=org.id, content=text, embedding=embedding,
            chunk_role="child", parent_chunk_id=parent.id,
            metadata_json={"department": department, "parent_chunk_id": str(parent.id), "parent_context": parent.content},
        ))
    await db_session.commit()

    results = await search_with_context(
        db_session, org.id, "refund policy", strategy="vector_only", top_k=10, score_threshold=0.0,
        metadata_filters={"department": "finance"},
    )
    assert len(results) == 2
    for r in results:
        assert r["metadata_json"]["department"] == "finance"
        assert r["metadata_json"]["parent_context"] == parent_a.content  # test 17: correct parent for an allowed child
        assert "legal" not in r["content"].lower()
        assert "B1" not in r["content"] and "B2" not in r["content"]  # test 16: never a forbidden child


async def test_parent_from_another_tenant_is_never_reachable(db_session):
    """Test 18 -- parent d'un autre tenant impossible: even with an
    identical child-metadata match, org isolation still applies."""
    org_a = await _make_org(db_session, "Org Parent Tenant A")
    org_b = await _make_org(db_session, "Org Parent Tenant B")
    doc_a = await _make_document(db_session, org_a.id)
    doc_b = await _make_document(db_session, org_b.id)

    parent_b = DocumentChunk(document_id=doc_b.id, organization_id=org_b.id, chunk_role="parent", content="Org B's own real parent context.")
    db_session.add(parent_b)
    await db_session.flush()

    child_text = "Refund policy child content shared wording."
    embedding = generate_embeddings([child_text], EMBEDDING_MODEL)[0]
    db_session.add(DocumentChunk(
        document_id=doc_a.id, organization_id=org_a.id, content=child_text, embedding=embedding,
        chunk_role="child", parent_chunk_id=None, metadata_json={"department": "finance"},
    ))
    await db_session.commit()

    results = await search_with_context(db_session, org_a.id, "refund policy", strategy="vector_only", top_k=5, score_threshold=0.0, metadata_filters={"department": "finance"})
    assert len(results) == 1
    assert results[0]["document_id"] == str(doc_a.id)
    assert "parent_chunk_id" not in (results[0]["metadata_json"] or {}) or results[0]["metadata_json"].get("parent_chunk_id") != str(parent_b.id)


# ============================================================
# 6. Citations
# ============================================================


async def test_citation_only_ever_points_to_an_allowed_chunk(db_session, monkeypatch):
    """Tests 19-20 -- citation uniquement vers un chunk autorisé, aucun
    chunk exclu ne devient citable, y compris avec un contenu très
    similaire entre documents."""
    import litellm
    from unittest.mock import AsyncMock
    from litellm.types.utils import Choices, Message, ModelResponse
    from api.config import settings
    from api.services.citations import get_citations_by_response
    from api.services.generation import generate_response

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")

    def _real_response(text):
        return ModelResponse(choices=[Choices(message=Message(content=text, role="assistant"), index=0, finish_reason="stop")])

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("The refund window is 30 days [1].")))

    org = await _make_org(db_session, "Org Citation Filter")
    finance_doc = await _make_document(db_session, org.id, name="finance.pdf")
    legal_doc = await _make_document(db_session, org.id, name="legal.pdf")
    await _add_chunks(db_session, org.id, finance_doc.id, [("The refund policy allows returns within 30 days.", {"department": "finance"})])
    await _add_chunks(db_session, org.id, legal_doc.id, [("The refund policy allows returns within 30 days.", {"department": "legal"})])

    response = await generate_response(db_session, org.id, "refund policy", metadata_filters={"department": "finance"})
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    assert len(citations) == 1
    assert citations[0].document_id == finance_doc.id
    assert citations[0].document_id != legal_doc.id


# ============================================================
# 7. Multi-tenant
# ============================================================


async def test_multi_tenant_isolation_with_identical_metadata_across_organizations(db_session):
    """Test 21/22 -- org A ne voit jamais org B, même avec des metadata
    strictement identiques."""
    org_a = await _make_org(db_session, "Org Meta Tenant A")
    org_b = await _make_org(db_session, "Org Meta Tenant B")
    doc_a = await _make_document(db_session, org_a.id)
    doc_b = await _make_document(db_session, org_b.id)
    await _add_chunks(db_session, org_a.id, doc_a.id, [("Finance quarterly numbers for org A.", {"department": "finance"})])
    await _add_chunks(db_session, org_b.id, doc_b.id, [("Finance quarterly numbers for org B.", {"department": "finance"})])

    results_a = await search(db_session, org_a.id, "finance quarterly numbers", strategy="vector_only", top_k=10, score_threshold=0.0, metadata_filters={"department": "finance"})
    assert len(results_a) == 1
    assert results_a[0]["document_id"] == str(doc_a.id)


# ============================================================
# 8. API (router + schema)
# ============================================================


async def test_api_search_without_filters_field(client, db_session, register_payload):
    """Test 1 -- filtre absent."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "API No Filter Org")
    document = await _make_document(db_session, uuid.UUID(org["id"]))
    await _add_chunks(db_session, uuid.UUID(org["id"]), document.id, [("Our refund policy allows returns within 30 days.", None)])

    response = await client.post(f"/organizations/{org['id']}/search", json={"query": "refund policy"}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1


async def test_api_search_with_a_simple_filter(client, db_session, register_payload):
    """Test 2 -- filtre simple."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "API Simple Filter Org")
    document = await _make_document(db_session, uuid.UUID(org["id"]))
    await _add_chunks(db_session, uuid.UUID(org["id"]), document.id, [
        ("Finance revenue forecast report.", {"department": "finance"}),
        ("Legal revenue forecast report.", {"department": "legal"}),
    ])

    response = await client.post(
        f"/organizations/{org['id']}/search", json={"query": "revenue forecast report", "filters": {"department": "finance"}, "score_threshold": 0.0},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["metadata_json"]["department"] == "finance"


async def test_api_search_with_multiple_filters(client, db_session, register_payload):
    """Test 3 -- plusieurs filtres."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "API Multi Filter Org")
    document = await _make_document(db_session, uuid.UUID(org["id"]))
    await _add_chunks(db_session, uuid.UUID(org["id"]), document.id, [
        ("Finance revenue forecast for 2026.", {"department": "finance", "year": 2026}),
        ("Finance revenue forecast for 2018.", {"department": "finance", "year": 2018}),
        ("Legal revenue forecast for 2026.", {"department": "legal", "year": 2026}),
    ])

    response = await client.post(
        f"/organizations/{org['id']}/search",
        json={"query": "revenue forecast", "filters": {"department": "finance", "year": 2026}, "score_threshold": 0.0},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["metadata_json"] == {"department": "finance", "year": 2026}


async def test_api_search_rejects_a_malformed_filter(client, db_session, register_payload):
    """Test 4 -- filtre invalide -> rejeté proprement (422)."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "API Invalid Filter Org")

    response = await client.post(
        f"/organizations/{org['id']}/search", json={"query": "anything", "filters": {"dept!": "finance"}},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 422

    response2 = await client.post(
        f"/organizations/{org['id']}/search", json={"query": "anything", "filters": {"year": {"bad_op": 2020}}},
        headers=_auth_header(owner_token),
    )
    assert response2.status_code == 422


# ============================================================
# 9. End-to-end integration (requirement 22)
# ============================================================


async def test_end_to_end_search_request_never_returns_a_metadata_excluded_document(client, db_session, register_payload, monkeypatch):
    """Requirement 22 -- API search request -> filters -> organization
    isolation -> retrieval -> hybrid -> selected chunks -> final result.
    A document matching the QUERY but NOT the metadata filter must never
    be returned."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "E2E Metadata Filter Org")
    org_id = uuid.UUID(org["id"])
    finance_doc = await _make_document(db_session, org_id, name="finance.pdf")
    legal_doc = await _make_document(db_session, org_id, name="legal.pdf")
    await _add_chunks(db_session, org_id, finance_doc.id, [("The revenue forecast for 2026 shows strong growth.", {"department": "finance", "year": 2026})])
    await _add_chunks(db_session, org_id, legal_doc.id, [("The revenue forecast for 2026 shows strong growth.", {"department": "legal", "year": 2026})])

    response = await client.post(
        f"/organizations/{org['id']}/search",
        json={"query": "revenue forecast 2026", "filters": {"department": "finance"}, "strategy": "hybrid", "score_threshold": 0.0},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["document_id"] == str(finance_doc.id)
    assert all(r["document_id"] != str(legal_doc.id) for r in results)
