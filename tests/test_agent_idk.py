"""Partie 6.2.3 -- "I don't know" threshold. Fast SQLite suite."""

import uuid

import pytest

from api.config import settings
from api.models.agent import Agent
from api.services.agent_idk import (
    DEFAULT_IDK_MESSAGE, InvalidIdkThresholdError, format_idk_response, get_idk_message, get_idk_threshold,
    should_say_idk, validate_idk_threshold,
)


async def _make_agent(db_session, org_id, **overrides):
    agent = Agent(organization_id=org_id, name="Bot", system_prompt="You are helpful.", **overrides)
    db_session.add(agent)
    await db_session.commit()
    return agent


# --------------------------------------- get_idk_threshold --


async def test_get_idk_threshold_returns_the_real_configured_value(db_session):
    """Validation criterion: le seuil de confiance fonctionne."""
    agent = await _make_agent(db_session, uuid.uuid4(), idk_threshold=0.6)
    assert await get_idk_threshold(db_session, agent.id) == 0.6


async def test_get_idk_threshold_falls_back_to_the_real_platform_default(db_session):
    agent = await _make_agent(db_session, uuid.uuid4())
    assert await get_idk_threshold(db_session, agent.id) == settings.IDK_THRESHOLD_DEFAULT


# --------------------------------------- should_say_idk --


def test_should_say_idk_true_below_the_real_threshold():
    """Validation criterion: le seuil est atteint."""
    assert should_say_idk(0.1, 0.3) is True


def test_should_say_idk_false_at_or_above_the_real_threshold():
    """Validation criterion: le seuil n'est pas atteint."""
    assert should_say_idk(0.5, 0.3) is False
    assert should_say_idk(0.3, 0.3) is False


def test_should_say_idk_is_honestly_false_for_a_real_missing_score():
    """Validation criterion: robustesse -- score de confiance manquant."""
    assert should_say_idk(None, 0.3) is False


# --------------------------------------- get_idk_message / format --


async def test_get_idk_message_returns_the_real_custom_message(db_session):
    """Validation criterion: le message personnalisé est affiché."""
    agent = await _make_agent(db_session, uuid.uuid4(), idk_message="Custom IDK.")
    assert await get_idk_message(db_session, agent.id) == "Custom IDK."


async def test_get_idk_message_falls_back_to_the_real_default(db_session):
    agent = await _make_agent(db_session, uuid.uuid4())
    assert await get_idk_message(db_session, agent.id) == DEFAULT_IDK_MESSAGE


def test_format_idk_response_falls_back_for_a_blank_message():
    assert format_idk_response("") == DEFAULT_IDK_MESSAGE


# --------------------------------------- validate_idk_threshold --


def test_validate_idk_threshold_accepts_a_real_in_bounds_value():
    validate_idk_threshold(0.5)
    validate_idk_threshold(None)


def test_validate_idk_threshold_rejects_a_real_out_of_bounds_value():
    """Validation criterion: les valeurs invalides sont rejetées."""
    with pytest.raises(InvalidIdkThresholdError):
        validate_idk_threshold(1.5)
    with pytest.raises(InvalidIdkThresholdError):
        validate_idk_threshold(-0.1)
