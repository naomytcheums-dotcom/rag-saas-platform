"""Partie 5.1.2 -- tests for api/services/tool_selection.py. The real,
deterministic heuristic path (rank_tools/filter_tools_by_capability/
select_tools with use_llm=False) is tested for real, no mocking. The
LLM path mocks litellm.acompletion at the same boundary as every other
LLM-backed module in this codebase."""

import json
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.services.tool_selection import filter_tools_by_capability, rank_tools, select_tools
from api.services.tools import CALCULATOR_TOOL, WORD_COUNT_TOOL, ToolSpec


def _response(text: str) -> ModelResponse:
    return ModelResponse(choices=[Choices(message=Message(content=text, role="assistant"), index=0, finish_reason="stop")])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


# ------------------------------------- rank_tools -------------------------------------


def test_rank_tools_scores_a_relevant_tool_higher():
    """Validation criterion: le classement fonctionne."""
    ranked = rank_tools("I need a calculator for math", [CALCULATOR_TOOL, WORD_COUNT_TOOL])
    assert ranked[0][0] is CALCULATOR_TOOL
    assert ranked[0][1] > ranked[1][1]


def test_rank_tools_returns_zero_scores_for_an_empty_query():
    ranked = rank_tools("", [CALCULATOR_TOOL, WORD_COUNT_TOOL])
    assert all(score == 0.0 for _, score in ranked)


# ------------------------------------- filter_tools_by_capability -------------------------------------


def test_filter_tools_by_capability_matches_a_real_tag():
    """Validation criterion: le filtrage fonctionne."""
    result = filter_tools_by_capability("I need some math help", [CALCULATOR_TOOL, WORD_COUNT_TOOL])
    assert result == [CALCULATOR_TOOL]


def test_filter_tools_by_capability_returns_empty_when_nothing_matches():
    assert filter_tools_by_capability("what's the weather", [CALCULATOR_TOOL, WORD_COUNT_TOOL]) == []


# ------------------------------------- select_tools (heuristic) -------------------------------------


async def test_select_tools_respects_top_k():
    """Validation criterion: les paramètres sont respectés."""
    tools = [CALCULATOR_TOOL, WORD_COUNT_TOOL]
    result = await select_tools("math and text", tools, use_llm=False, threshold=0.0, top_k=1)
    assert len(result) == 1


async def test_select_tools_respects_threshold():
    result = await select_tools("completely unrelated topic xyz", [CALCULATOR_TOOL], use_llm=False, threshold=0.9)
    assert result == []


async def test_select_tools_returns_empty_list_for_no_available_tools():
    """Validation criterion: robustesse -- que se passe-t-il si aucun
    outil n'est sélectionné (ici : aucun outil disponible)."""
    assert await select_tools("anything", [], use_llm=False) == []


# ------------------------------------- select_tools (LLM path) -------------------------------------


async def test_select_tools_via_llm_parses_a_real_json_response(monkeypatch):
    """Validation criterion: la sélection d'outils fonctionne (chemin LLM)."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_response(json.dumps(["calculator"]))))

    result = await select_tools("what is 5 * 5", [CALCULATOR_TOOL, WORD_COUNT_TOOL], use_llm=True)
    assert result == [CALCULATOR_TOOL]


async def test_select_tools_via_llm_falls_back_to_heuristic_on_malformed_response(monkeypatch):
    """Validation criterion: robustesse -- une réponse LLM invalide ne
    doit jamais faire planter la sélection, elle doit retomber sur le
    chemin déterministe réel."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_response("not valid json at all")))

    result = await select_tools("2 + 2", [CALCULATOR_TOOL, WORD_COUNT_TOOL], use_llm=True, threshold=0.0)
    assert CALCULATOR_TOOL in result


async def test_select_tools_via_llm_falls_back_to_heuristic_on_none_content(monkeypatch):
    """Phase 5, Étape 6 correctif -- a real, previously-latent bug: a
    provider message with no real text content (`content=None`, only
    possible in this codebase now that real function-calling responses
    exist) used to crash with an uncaught `AttributeError`
    (`None.strip()`) instead of falling back to the real heuristic
    ranker, same as any other malformed LLM reply."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_response(None)))

    result = await select_tools("2 + 2", [CALCULATOR_TOOL, WORD_COUNT_TOOL], use_llm=True, threshold=0.0)
    assert CALCULATOR_TOOL in result
