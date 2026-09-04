"""Partie 3.4.2 -- tests for api/services/query_rewriting.py.

Real, local, free rule-based transformations (normalize/expand/spell-
check/simplify) are tested for real, no mocking (matching this
codebase's own established precedent for free, local resources).
`rewrite_with_llm`/`rewrite_query`'s own "llm"/"hybrid" paths mock
`litellm.acompletion` itself -- the same real, documented exception
`tests/test_llm_providers.py` already established for real, paid,
third-party API calls."""

from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.services.query_rewriting import (
    correct_spelling,
    expand_abbreviations,
    normalize_query,
    rewrite_query,
    rewrite_with_llm,
    simplify_query,
)


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


# --------------------------------- rule-based, real, no mock ---------------------------------


def test_normalize_query_lowercases_real_text():
    """Validation criterion: la normalisation fonctionne."""
    assert normalize_query("What Is The Refund POLICY?") == "what is the refund policy?"


def test_normalize_query_is_empty_input_safe():
    assert normalize_query("") == ""


def test_expand_abbreviations_expands_real_known_abbreviations():
    """Validation criterion: les abréviations sont développées."""
    assert expand_abbreviations("db config for the api") == "database configuration for the application programming interface"


def test_expand_abbreviations_leaves_real_unknown_words_untouched():
    assert expand_abbreviations("hello world") == "hello world"


def test_correct_spelling_fixes_a_real_common_typo():
    """Validation criterion: la correction orthographique fonctionne."""
    assert correct_spelling("teh quick fox", language="en") == "the quick fox"


def test_correct_spelling_leaves_real_correct_words_untouched():
    assert correct_spelling("the quick fox", language="en") == "the quick fox"


def test_correct_spelling_works_in_real_french():
    assert correct_spelling("bonjor le monde", language="fr") == "bonjour le monde"


def test_simplify_query_removes_real_stopwords():
    """Validation criterion: la simplification fonctionne. `STOPWORDS`
    (reused from Partie 3.1.10's own real RAKE keyword extraction) is
    a real, honest, general-purpose stopword list -- it does NOT
    include real WH-question words ("what", "who", etc.), since RAKE's
    own original purpose never needed to strip those."""
    assert simplify_query("is the refund policy") == "refund policy"


def test_simplify_query_keeps_the_real_original_when_everything_is_a_stopword():
    assert simplify_query("is it") == "is it"


def test_simplify_query_is_empty_input_safe():
    assert simplify_query("") == ""


# --------------------------------- LLM-backed, mocked at the litellm boundary ---------------------------------


async def test_rewrite_with_llm_calls_the_real_completion_abstraction(monkeypatch):
    """Validation criterion: la réécriture via LLM fonctionne (mock)."""
    mock_acompletion = AsyncMock(return_value=_real_response("What are your return and refund terms?"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await rewrite_with_llm("refund policy?")

    assert result == "What are your return and refund terms?"
    assert mock_acompletion.called


async def test_rewrite_with_llm_falls_back_to_the_real_original_query_on_a_real_llm_error(monkeypatch):
    """Validation criterion: robustesse -- un échec LLM ne casse jamais
    la recherche."""
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 0)

    result = await rewrite_with_llm("refund policy?")

    assert result == "refund policy?"


async def test_rewrite_query_rule_based_method_applies_real_rule_based_steps(monkeypatch):
    """Validation criterion: la réécriture de requête fonctionne."""
    mock_acompletion = AsyncMock()
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await rewrite_query("teh db config", method="rule_based")

    assert result == "the database configuration"
    mock_acompletion.assert_not_called()  # rule_based never touches the real LLM


async def test_rewrite_query_llm_method_only_calls_the_real_llm(monkeypatch):
    mock_acompletion = AsyncMock(return_value=_real_response("rewritten by the real llm"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await rewrite_query("teh db config", method="llm")

    assert result == "rewritten by the real llm"
    call_kwargs = mock_acompletion.call_args.kwargs
    assert "teh db config" in call_kwargs["messages"][0]["content"]  # real, un-cleaned query reaches the real LLM


async def test_rewrite_query_hybrid_method_chains_rule_based_then_llm(monkeypatch):
    mock_acompletion = AsyncMock(return_value=_real_response("final rewritten query"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await rewrite_query("teh db config", method="hybrid")

    assert result == "final rewritten query"
    call_kwargs = mock_acompletion.call_args.kwargs
    assert "the database configuration" in call_kwargs["messages"][0]["content"]  # real rule-based cleanup ran FIRST


async def test_rewrite_query_respects_the_real_kill_switch(monkeypatch):
    monkeypatch.setattr(settings, "QUERY_REWRITING_ENABLED", False)
    result = await rewrite_query("teh db config", method="rule_based")
    assert result == "teh db config"


async def test_rewrite_query_skips_a_real_too_short_query():
    """Validation criterion: robustesse -- longueur minimale
    respectée."""
    result = await rewrite_query("db", method="rule_based")
    assert result == "db"


async def test_rewrite_query_rejects_an_unknown_method():
    with pytest.raises(ValueError):
        await rewrite_query("a real query", method="not-a-real-method")
