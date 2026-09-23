"""Partie 6.1.1 -- real, multi-tenant generate_response. Real litellm
mock at the same boundary as tests/test_agent_orchestrator.py;
search_with_context mocked at its own clean, already-tested boundary
(real end-to-end retrieval is covered by tests/test_retrieval_pipeline.py)."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.organization import Organization
from api.services.citations import get_citations_by_response
from api.services.generation import generate_response


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


def _fake_chunks():
    return [
        {"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": "The sky scatters blue light.",
         "score": 0.9, "document_name": "physics.pdf", "file_type": "application/pdf"},
    ]


async def test_generate_response_persists_a_real_response(monkeypatch, db_session):
    """Validation criterion: la génération avec citations fonctionne."""
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=_fake_chunks()))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("The sky is blue [1].")))

    org = await _make_org(db_session, "Generation Org")
    await db_session.commit()

    response = await generate_response(db_session, org.id, "Why is the sky blue?")
    await db_session.commit()

    assert response.query == "Why is the sky blue?"
    assert response.answer == "The sky is blue [1]."
    assert response.organization_id == org.id


async def test_generate_response_prefers_the_real_parent_context_when_present(monkeypatch, db_session):
    """Phase 4, Étape 1 (correctif parent_child) -- validation criterion:
    l'assemblage du contexte LLM privilégie le vrai contexte parent
    (plus large) quand un vrai child en porte un, sans jamais changer ce
    qu'une vraie citation affiche (toujours le content précis du child)."""
    chunk = {
        "chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()),
        "content": "The precise child sentence.",
        "metadata_json": {"chunking_strategy": "parent_child", "parent_context": "A much wider real parent paragraph giving full context."},
        "score": 0.9, "document_name": "d.pdf", "file_type": "application/pdf",
    }
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=[chunk]))
    mock_acompletion = AsyncMock(return_value=_real_response("An answer [1]."))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Generation Org Parent Child")
    await db_session.commit()
    response = await generate_response(db_session, org.id, "A question")
    await db_session.commit()

    system_prompt = mock_acompletion.call_args.kwargs["messages"][0]["content"]
    assert "A much wider real parent paragraph giving full context." in system_prompt
    assert "The precise child sentence." not in system_prompt  # the narrower child text was really replaced, not just appended

    citations = await get_citations_by_response(db_session, response.id)
    assert citations[0].text == "The precise child sentence."  # a real citation still points at the child's own precise content


async def test_generate_response_attaches_real_citations_by_default(monkeypatch, db_session):
    """Validation criterion: 5 citations par défaut."""
    chunks = [{"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": f"chunk {i}", "score": 0.9 - i * 0.05,
               "document_name": "d.pdf", "file_type": "pdf"} for i in range(8)]
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=chunks))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Generation Org 2")
    await db_session.commit()
    response = await generate_response(db_session, org.id, "A question")
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    assert len(citations) == settings.CITATION_DEFAULT_COUNT


async def test_generate_response_includes_real_context_in_the_real_prompt(monkeypatch, db_session):
    """Validation criterion: cohérence -- RAG_search retourne les
    sources et elles nourrissent réellement le prompt."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=_fake_chunks()))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Generation Org 3")
    await db_session.commit()
    await generate_response(db_session, org.id, "Why is the sky blue?")

    system_message = mock_acompletion.call_args.kwargs["messages"][0]["content"]
    assert "scatters blue light" in system_message
    assert "[1]" in system_message


async def test_generate_response_works_with_no_real_chunks_found(monkeypatch, db_session):
    """Validation criterion: robustesse -- pas de crash sans contexte réel."""
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("I don't have information on that.")))

    org = await _make_org(db_session, "Generation Org 4")
    await db_session.commit()
    response = await generate_response(db_session, org.id, "An unanswerable question")
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    assert citations == []


async def test_generate_response_respects_a_real_custom_citation_count(monkeypatch, db_session):
    chunks = [{"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": f"c{i}", "score": 0.9, "document_name": "d.pdf", "file_type": "pdf"} for i in range(3)]
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=chunks))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("ok")))

    org = await _make_org(db_session, "Generation Org 5")
    await db_session.commit()
    response = await generate_response(db_session, org.id, "q", citation_count=1)
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    assert len(citations) == 1


# ---------------------- Phase 4, Étape 2 (Advanced Retrieval) -- Context Compression ----------------------


async def test_generate_response_compresses_context_when_enabled(monkeypatch, db_session):
    """Validation criterion: la compression réduit le bruit avant
    génération, sans jamais casser les citations (requirement 9) --
    `add_citations_to_response` is always called with the real,
    UNCOMPRESSED chunks, only the real LLM prompt text changes."""
    import api.services.context_compression as compression_module
    from api.models.organization_settings import OrganizationSettings

    chunk = {
        "chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()),
        "content": "The original, full, uncompressed real chunk content.",
        "score": 0.9, "document_name": "d.pdf", "file_type": "pdf",
    }
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=[chunk]))
    mock_acompletion = AsyncMock(return_value=_real_response("An answer [1]."))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    async def _fake_compress(chunks, max_tokens=None, method=None, query=None, **kwargs):
        return [{**c, "content": "COMPRESSED"} for c in chunks]

    monkeypatch.setattr(compression_module, "compress_context", _fake_compress)

    org = await _make_org(db_session, "Generation Org Compression")
    db_session.add(OrganizationSettings(organization_id=org.id, settings={"context_compression_enabled": True}))
    await db_session.commit()

    response = await generate_response(db_session, org.id, "A question")
    await db_session.commit()

    system_prompt = mock_acompletion.call_args.kwargs["messages"][0]["content"]
    assert "COMPRESSED" in system_prompt
    assert "The original, full, uncompressed real chunk content." not in system_prompt

    citations = await get_citations_by_response(db_session, response.id)
    assert citations[0].text == "The original, full, uncompressed real chunk content."


async def test_generate_response_context_compression_is_disabled_by_default(monkeypatch, db_session):
    """Validation criterion: rétrocompatibilité -- a real organization
    that never touches context_compression_enabled never even calls
    compress_context."""
    import api.services.context_compression as compression_module

    chunk = {
        "chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()),
        "content": "Full content that must remain uncompressed.",
        "score": 0.9, "document_name": "d.pdf", "file_type": "pdf",
    }
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=[chunk]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("ok")))
    mock_compress = AsyncMock()
    monkeypatch.setattr(compression_module, "compress_context", mock_compress)

    org = await _make_org(db_session, "Generation Org Compression Default")
    await db_session.commit()
    await generate_response(db_session, org.id, "q")

    mock_compress.assert_not_called()


async def test_generate_response_falls_back_when_compression_fails(monkeypatch, db_session):
    """Validation criterion: robustesse -- un échec de compression ne
    casse jamais la génération (requirement 9's own explicit ask)."""
    import api.services.context_compression as compression_module
    from api.models.organization_settings import OrganizationSettings

    chunk = {
        "chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()),
        "content": "Real content that must survive a compression failure.",
        "score": 0.9, "document_name": "d.pdf", "file_type": "pdf",
    }
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=[chunk]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("ok")))

    async def _boom(*args, **kwargs):
        raise RuntimeError("a real, simulated compression failure")

    monkeypatch.setattr(compression_module, "compress_context", _boom)

    org = await _make_org(db_session, "Generation Org Compression Failure")
    db_session.add(OrganizationSettings(organization_id=org.id, settings={"context_compression_enabled": True}))
    await db_session.commit()

    response = await generate_response(db_session, org.id, "q")
    await db_session.commit()

    assert response.answer == "ok"
    citations = await get_citations_by_response(db_session, response.id)
    assert citations[0].text == "Real content that must survive a compression failure."


async def test_generate_response_llm_compression_preserves_per_chunk_citation_mapping(monkeypatch, db_session):
    """Phase 4, Étape 2 correctif ciblé (2026-09-22) -- real, end-to-end
    regression test for the real `context_compression.py` traceability
    fix: with `method="llm"` and 3 real, distinct chunks, each real
    compressed block in the real LLM prompt still corresponds 1:1 to its
    own real, original source chunk (`[1]`->A, `[2]`->B, `[3]`->C), and
    real citations still resolve to the real, UNCOMPRESSED original
    content -- never the compressed paraphrase, never a merged blob."""
    from api.models.organization_settings import OrganizationSettings

    chunks = [
        {"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()),
         "content": "UNIQUE_A original real content with quite a lot of extra padding words to make it long.",
         "score": 0.9, "document_name": "a.pdf", "file_type": "pdf"},
        {"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()),
         "content": "UNIQUE_B original real content with quite a lot of extra padding words to make it long.",
         "score": 0.8, "document_name": "b.pdf", "file_type": "pdf"},
        {"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()),
         "content": "UNIQUE_C original real content with quite a lot of extra padding words to make it long.",
         "score": 0.7, "document_name": "c.pdf", "file_type": "pdf"},
    ]
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=chunks))

    # 3 real, distinct per-chunk compression calls (one real LLM call per
    # real chunk, per context_compression.py's own real fix), then 1 real
    # final generation call.
    mock_acompletion = AsyncMock(side_effect=[
        _real_response("compressed UNIQUE_A"), _real_response("compressed UNIQUE_B"),
        _real_response("compressed UNIQUE_C"), _real_response("Answer citing [1], [2], [3]."),
    ])
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(settings, "CONTEXT_COMPRESSION_METHOD", "llm")
    # Small enough that the real, padded ORIGINAL chunks (above) genuinely
    # exceed it (so compression really triggers), but large enough that
    # the real, tiny mocked "compressed UNIQUE_X" outputs all still fit
    # afterward (so the real, post-compression `truncate_to_limit` never
    # drops one -- isolating the real 1:1 mapping this test checks from
    # truncation, the same real reasoning as
    # tests/test_context_compression.py's own equivalent test).
    monkeypatch.setattr(settings, "CONTEXT_COMPRESSION_MAX_TOKENS", 15)

    org = await _make_org(db_session, "Generation Org LLM Compression Mapping")
    db_session.add(OrganizationSettings(organization_id=org.id, settings={"context_compression_enabled": True}))
    await db_session.commit()

    response = await generate_response(db_session, org.id, "What is UNIQUE_A?")
    await db_session.commit()

    system_prompt = mock_acompletion.call_args_list[-1].kwargs["messages"][0]["content"]
    assert "[1] compressed UNIQUE_A" in system_prompt
    assert "[2] compressed UNIQUE_B" in system_prompt
    assert "[3] compressed UNIQUE_C" in system_prompt
    assert mock_acompletion.call_count == 4

    citations = await get_citations_by_response(db_session, response.id)
    citations_by_number = {c.citation_number: c for c in citations}
    assert citations_by_number[1].text == chunks[0]["content"]
    assert citations_by_number[1].chunk_id == uuid.UUID(chunks[0]["chunk_id"])
    assert citations_by_number[2].text == chunks[1]["content"]
    assert citations_by_number[3].text == chunks[2]["content"]
