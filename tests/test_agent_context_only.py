"""Partie 6.2.2 -- answer only from context. Fast SQLite suite."""

import uuid

from api.config import settings
from api.models.agent import Agent
from api.services.agent_context_only import (
    DEFAULT_CONTEXT_ONLY_MESSAGE, format_context_only_response, get_context_only_message, is_answer_only_from_context,
    validate_response_in_context,
)


async def _make_agent(db_session, org_id, **overrides):
    agent = Agent(organization_id=org_id, name="Bot", system_prompt="You are helpful.", **overrides)
    db_session.add(agent)
    await db_session.commit()
    return agent


# --------------------------------------- is_answer_only_from_context --


async def test_is_answer_only_from_context_reflects_the_real_agent_field(db_session):
    """Validation criterion: le mode contexte uniquement fonctionne."""
    agent = await _make_agent(db_session, uuid.uuid4(), answer_only_from_context=True)
    assert await is_answer_only_from_context(db_session, agent.id) is True


async def test_is_answer_only_from_context_is_honestly_false_by_default(db_session):
    agent = await _make_agent(db_session, uuid.uuid4())
    assert await is_answer_only_from_context(db_session, agent.id) is False


# --------------------------------------- validate_response_in_context --


def test_validate_response_in_context_is_true_for_a_real_grounded_answer():
    """Validation criterion: la similarité est vérifiée."""
    assert validate_response_in_context(
        "Rayleigh scattering explains why the sky is blue.", "Rayleigh scattering explains why the sky is blue.",
    ) is True


def test_validate_response_in_context_is_false_for_a_real_ungrounded_answer():
    assert validate_response_in_context(
        "The stock market crashed due to unrelated economic factors.", "Rayleigh scattering explains why the sky is blue.",
    ) is False


def test_validate_response_in_context_is_honestly_false_for_an_empty_real_context():
    """Validation criterion: robustesse -- contexte vide."""
    assert validate_response_in_context("Any real answer.", "") is False


def test_validate_response_in_context_strict_mode_fails_on_one_real_ungrounded_claim(monkeypatch):
    monkeypatch.setattr(settings, "CONTEXT_ONLY_STRICT", True)
    answer = "Rayleigh scattering explains the sky's color. The stock market crashed yesterday."
    context = "Rayleigh scattering explains the sky's color."
    assert validate_response_in_context(answer, context) is False


def test_validate_response_in_context_non_strict_mode_uses_the_real_overall_average(monkeypatch):
    monkeypatch.setattr(settings, "CONTEXT_ONLY_STRICT", False)
    monkeypatch.setattr(settings, "CONTEXT_ONLY_SIMILARITY_THRESHOLD", 0.1)
    answer = "Rayleigh scattering explains the sky's color. A brief, unrelated aside."
    context = "Rayleigh scattering explains the sky's color."
    assert validate_response_in_context(answer, context) is True


# --------------------------------------- get_context_only_message / format --


async def test_get_context_only_message_returns_the_real_custom_message(db_session):
    """Validation criterion: le message personnalisé est affiché."""
    agent = await _make_agent(db_session, uuid.uuid4(), answer_only_from_context=True, context_only_message="Custom refusal.")
    assert await get_context_only_message(db_session, agent.id) == "Custom refusal."


async def test_get_context_only_message_falls_back_to_the_real_default(db_session):
    agent = await _make_agent(db_session, uuid.uuid4(), answer_only_from_context=True)
    assert await get_context_only_message(db_session, agent.id) == DEFAULT_CONTEXT_ONLY_MESSAGE


def test_format_context_only_response_falls_back_for_a_blank_message():
    assert format_context_only_response("") == DEFAULT_CONTEXT_ONLY_MESSAGE
