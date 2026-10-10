"""Specs 13.2.7, 13.2.8 - tests against a REAL language model. Opt-in: they cost a few cents and need a network, so they never run by default.

    RUN_REAL_LLM_TESTS=1 ANTHROPIC_API_KEY=... pytest tests/llm_optin -q

Without the switch every test here is skipped, so the normal suite and CI stay free and deterministic. The manual workflow
`.github/workflows/llm-tests.yml` runs them with the repository secret ANTHROPIC_API_KEY.
"""

import os

import pytest

from api.services.llm_providers import chat_completion

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_REAL_LLM_TESTS") != "1" or not os.environ.get("ANTHROPIC_API_KEY"),
    reason="real-LLM tests are opt-in: set RUN_REAL_LLM_TESTS=1 and ANTHROPIC_API_KEY",
)

PASSAGE = "Policy 4.2 - Refunds. Customers may request a refund within 30 days of purchase. After 30 days no refund is possible."


async def _ask(question: str) -> str:
    messages = [
        {"role": "system", "content": "Answer only from the passage. If the passage does not contain the answer, reply exactly: I do not know."},
        {"role": "user", "content": f"Passage:\n{PASSAGE}\n\nQuestion: {question}"},
    ]
    return await chat_completion(messages, provider="anthropic", model=os.environ.get("REAL_LLM_TEST_MODEL", "claude-haiku-5-5"), max_tokens=100)


async def test_the_model_answers_a_question_from_the_passage():
    answer = await _ask("How many days do customers have to request a refund?")
    assert "30" in answer


async def test_the_model_declines_a_question_the_passage_cannot_answer():
    answer = await _ask("What is the capital of Australia?")
    assert "do not know" in answer.lower()
    assert "canberra" not in answer.lower()
