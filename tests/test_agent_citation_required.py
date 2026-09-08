"""Partie 6.2.1 -- citation-required mode. Fast SQLite suite."""

import uuid

from api.models.agent import Agent
from api.models.citation import Citation
from api.services.agent_citation_required import (
    DEFAULT_CITATION_REQUIRED_MESSAGE, format_citation_required_response, get_citation_required_message,
    is_citation_required, validate_response_has_citations,
)


async def _make_agent(db_session, org_id, **overrides):
    agent = Agent(organization_id=org_id, name="Bot", system_prompt="You are helpful.", **overrides)
    db_session.add(agent)
    await db_session.commit()
    return agent


def _citation(number=1):
    return Citation(response_id=uuid.uuid4(), text="Some cited text.", relevance_score=0.9, citation_number=number)


# --------------------------------------- is_citation_required --


async def test_is_citation_required_reflects_the_real_agent_field(db_session):
    """Validation criterion: le mode citation obligatoire fonctionne."""
    agent = await _make_agent(db_session, uuid.uuid4(), citation_required=True)
    assert await is_citation_required(db_session, agent.id) is True


async def test_is_citation_required_is_honestly_false_by_default(db_session):
    agent = await _make_agent(db_session, uuid.uuid4())
    assert await is_citation_required(db_session, agent.id) is False


async def test_is_citation_required_is_honestly_false_for_an_unknown_agent(db_session):
    assert await is_citation_required(db_session, uuid.uuid4()) is False


# --------------------------------------- validate_response_has_citations --


def test_validate_response_has_citations_true_with_real_citations():
    """Validation criterion: les citations sont vérifiées."""
    assert validate_response_has_citations([_citation()]) is True


def test_validate_response_has_citations_is_honestly_false_without_any():
    """Validation criterion: robustesse -- absence de citations."""
    assert validate_response_has_citations([]) is False


# --------------------------------------- get_citation_required_message / format --


async def test_get_citation_required_message_returns_the_real_custom_message(db_session):
    """Validation criterion: le message personnalisé est affiché."""
    agent = await _make_agent(db_session, uuid.uuid4(), citation_required=True, citation_required_message="Custom refusal.")
    assert await get_citation_required_message(db_session, agent.id) == "Custom refusal."


async def test_get_citation_required_message_falls_back_to_the_real_default(db_session):
    agent = await _make_agent(db_session, uuid.uuid4(), citation_required=True)
    assert await get_citation_required_message(db_session, agent.id) == DEFAULT_CITATION_REQUIRED_MESSAGE


def test_format_citation_required_response_falls_back_for_a_blank_message():
    assert format_citation_required_response("   ") == DEFAULT_CITATION_REQUIRED_MESSAGE
    assert format_citation_required_response("Real message.") == "Real message."
