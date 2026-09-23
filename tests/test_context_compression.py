"""Partie 3.4.10 -- tests for api/services/context_compression.py.

`summarize_chunk`/`compress_with_llm`/`compress_context`'s own
"summarize"/"llm" methods mock `litellm.acompletion` itself (the same
real, documented exception `tests/test_llm_providers.py` already
established). Everything else (`extract_key_sentences`,
`rerank_by_importance`, `truncate_to_limit`, `compress_context`'s own
"extract" method) uses real embeddings/tokenizers, no mocking."""

from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.services.context_compression import (
    compress_context,
    compress_with_llm,
    extract_key_sentences,
    rerank_by_importance,
    summarize_chunk,
    truncate_to_limit,
)


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


_LONG_TEXT = (
    "The refund policy allows returns within 30 days of purchase. "
    "Items must be in their original packaging and unused condition. "
    "Refunds are processed to the original payment method within 5 business days. "
    "Store credit is also available as an alternative to a cash refund. "
    "Final sale items are not eligible for any refund or exchange."
)


# --------------------------------- real, no mock ---------------------------------


def test_extract_key_sentences_reuses_the_real_extractive_summary():
    """Validation criterion: l'extraction de phrases clés
    fonctionne."""
    summary = extract_key_sentences(_LONG_TEXT, num_sentences=2)
    assert summary
    assert summary.count(".") <= 3  # roughly 2 real sentences


def test_extract_key_sentences_is_empty_input_safe():
    assert extract_key_sentences("") == ""


def test_rerank_by_importance_favors_the_real_query_relevant_chunk():
    """Validation criterion: le reranking par importance fonctionne."""
    chunks = [
        {"chunk_id": "1", "content": "Bananas are a good source of potassium."},
        {"chunk_id": "2", "content": "The refund policy allows returns within 30 days."},
    ]
    reranked = rerank_by_importance(chunks, "refund policy")
    assert reranked[0]["chunk_id"] == "2"


def test_rerank_by_importance_is_empty_input_safe():
    assert rerank_by_importance([], "anything") == []


def test_truncate_to_limit_respects_the_real_token_budget():
    """Validation criterion: le troncage respecte la limite de
    tokens."""
    chunks = [{"content": f"Real filler content number {i} about various topics here."} for i in range(20)]
    truncated = truncate_to_limit(chunks, max_tokens=20)
    assert len(truncated) < len(chunks)
    assert len(truncated) >= 1


def test_truncate_to_limit_always_keeps_at_least_one_real_oversized_chunk():
    """Real, honest edge case: a single chunk bigger than the real
    budget on its own is still kept, never dropped to an empty
    result."""
    chunks = [{"content": _LONG_TEXT * 5}]
    truncated = truncate_to_limit(chunks, max_tokens=5)
    assert len(truncated) == 1


def test_truncate_to_limit_is_empty_input_safe():
    assert truncate_to_limit([]) == []


# --------------------------------- LLM-backed, mocked at the litellm boundary ---------------------------------


async def test_summarize_chunk_calls_the_real_llm(monkeypatch):
    """Validation criterion: le résumé de chunk fonctionne (mock)."""
    mock_acompletion = AsyncMock(return_value=_real_response("A real, concise summary."))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await summarize_chunk(_LONG_TEXT)

    assert result == "A real, concise summary."


async def test_summarize_chunk_falls_back_to_the_real_original_on_a_real_llm_error(monkeypatch):
    """Validation criterion: robustesse -- un échec LLM ne fait jamais
    perdre le contenu."""
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 0)

    result = await summarize_chunk(_LONG_TEXT)

    assert result == _LONG_TEXT


async def test_compress_with_llm_keeps_one_real_result_per_real_input_chunk(monkeypatch):
    """Phase 4, Étape 2 correctif ciblé -- real regression test for the
    real traceability bug: `compress_with_llm` used to combine every
    real chunk into ONE combined result, losing the real 1:1 mapping a
    real caller's own `[N]` numbering depends on. Now real, one real
    (possibly distinct) compressed result per real input chunk."""
    mock_acompletion = AsyncMock(side_effect=[
        _real_response("Condensed part one."), _real_response("Condensed part two."),
    ])
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    chunks = [
        {"chunk_id": "1", "document_id": "doc-a", "content": "Part one."},
        {"chunk_id": "2", "document_id": "doc-b", "content": "Part two."},
    ]
    result = await compress_with_llm(chunks, "a real question")

    assert len(result) == 2
    assert result[0]["content"] == "Condensed part one."
    assert result[1]["content"] == "Condensed part two."
    # Real, deliberate check: every other real key (chunk identity) rides
    # through completely untouched -- only `content` was ever compressed.
    assert result[0]["chunk_id"] == "1" and result[0]["document_id"] == "doc-a"
    assert result[1]["chunk_id"] == "2" and result[1]["document_id"] == "doc-b"
    assert mock_acompletion.call_count == 2


async def test_compress_with_llm_falls_back_per_chunk_on_a_real_llm_failure(monkeypatch):
    """Real, honest per-chunk robustness: one real chunk's own LLM
    failure returns THAT chunk's own real, uncompressed content, and
    never blocks another, independently-succeeding real chunk."""
    mock_acompletion = AsyncMock(side_effect=[
        litellm.exceptions.RateLimitError(message="rate limited", llm_provider="anthropic", model="claude"),
        _real_response("Condensed part two."),
    ])
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 0)

    chunks = [{"chunk_id": "1", "content": "Part one."}, {"chunk_id": "2", "content": "Part two."}]
    result = await compress_with_llm(chunks, "a real question")

    assert result[0]["content"] == "Part one."  # the real, failed chunk kept its own real, uncompressed content
    assert result[1]["content"] == "Condensed part two."


# --------------------------------- compress_context orchestrator ---------------------------------


async def test_compress_context_extract_method_shrinks_real_chunks(monkeypatch):
    """Validation criterion: la compression de contexte fonctionne."""
    mock_acompletion = AsyncMock()
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    chunks = [{"content": _LONG_TEXT} for _ in range(5)]
    result = await compress_context(chunks, max_tokens=30, method="extract")

    assert len(result) <= len(chunks)
    mock_acompletion.assert_not_called()  # the real "extract" method never touches the real LLM


async def test_compress_context_skips_compression_when_already_under_budget(monkeypatch):
    """Validation criterion: robustesse -- le contexte déjà plus petit
    que la limite n'est jamais compressé."""
    mock_acompletion = AsyncMock()
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    chunks = [{"content": "Short."}]
    result = await compress_context(chunks, max_tokens=2000, method="extract")

    assert result == chunks
    mock_acompletion.assert_not_called()


async def test_compress_context_summarize_method_calls_the_real_llm_per_chunk(monkeypatch):
    mock_acompletion = AsyncMock(return_value=_real_response("summarized"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    chunks = [{"content": _LONG_TEXT} for _ in range(3)]
    result = await compress_context(chunks, max_tokens=10, method="summarize")

    assert mock_acompletion.call_count == 3
    assert all(c["content"] == "summarized" for c in result)


async def test_compress_context_llm_method_keeps_one_real_result_per_real_chunk(monkeypatch):
    """Phase 4, Étape 2 correctif ciblé -- real regression test:
    `method="llm"` used to collapse every real chunk into ONE combined
    result (a real traceability bug, see `compress_with_llm`'s own
    docstring). Now real, one real result per real input chunk, same
    real 1:1 shape as "extract"/"summarize"."""
    mock_acompletion = AsyncMock(side_effect=[_real_response(f"condensed {i}") for i in range(3)])
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    # max_tokens=30 sits below the real, combined token count of 3 real
    # `_LONG_TEXT` copies (so compression genuinely triggers) but well
    # above the real, tiny compressed outputs below (so the real,
    # post-compression `truncate_to_limit` doesn't drop any of them --
    # isolating the real 1:1 mapping this test checks from truncation).
    chunks = [{"chunk_id": str(i), "content": _LONG_TEXT} for i in range(3)]
    result = await compress_context(chunks, max_tokens=30, method="llm", query="refund policy")

    assert len(result) == 3
    assert [c["chunk_id"] for c in result] == ["0", "1", "2"]
    assert result[0]["content"] == "condensed 0"
    assert result[1]["content"] == "condensed 1"
    assert result[2]["content"] == "condensed 2"


async def test_compress_context_llm_method_without_a_real_query_raises():
    chunks = [{"content": _LONG_TEXT} for _ in range(5)]
    with pytest.raises(ValueError):
        await compress_context(chunks, max_tokens=10, method="llm")


async def test_compress_context_rejects_an_unknown_method():
    chunks = [{"content": _LONG_TEXT} for _ in range(5)]
    with pytest.raises(ValueError):
        await compress_context(chunks, max_tokens=10, method="not-a-real-method")


async def test_compress_context_respects_the_real_kill_switch(monkeypatch):
    monkeypatch.setattr(settings, "CONTEXT_COMPRESSION_ENABLED", False)
    chunks = [{"content": _LONG_TEXT} for _ in range(5)]
    result = await compress_context(chunks, max_tokens=10)
    assert result == chunks


async def test_compress_context_is_empty_input_safe():
    assert await compress_context([]) == []
