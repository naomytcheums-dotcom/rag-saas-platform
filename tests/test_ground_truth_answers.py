"""Partie 7.1.3 -- ground-truth answers. Fast SQLite suite (real embeddings for semantic validation)."""

import uuid

import pytest

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.organization import Organization
from api.services.ground_truth_answers import (
    get_ground_truth, set_ground_truth, validate_answer, validate_contains, validate_exact_match, validate_fuzzy,
    validate_semantic,
)


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_question(db_session, org_id, question="Q?"):
    dataset = EvaluationDataset(organization_id=org_id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    row = EvaluationQuestion(dataset_id=dataset.id, question=question)
    db_session.add(row)
    await db_session.commit()
    return row


# --------------------------------------- validate_exact_match --


def test_validate_exact_match_is_case_and_whitespace_insensitive():
    """Validation criterion: la validation exacte fonctionne."""
    assert validate_exact_match(" Paris ", "paris") is True


def test_validate_exact_match_rejects_a_real_different_answer():
    assert validate_exact_match("London", "Paris") is False


def test_validate_exact_match_is_honestly_false_for_an_empty_answer():
    """Validation criterion: robustesse -- réponse vide."""
    assert validate_exact_match("", "Paris") is False


# --------------------------------------- validate_contains --


def test_validate_contains_finds_the_real_expected_substring():
    assert validate_contains("The capital of France is Paris.", "Paris") is True


def test_validate_contains_rejects_a_real_missing_substring():
    assert validate_contains("The capital of France is Paris.", "London") is False


# --------------------------------------- validate_semantic --


def test_validate_semantic_accepts_a_real_paraphrased_answer():
    """Validation criterion: la validation sémantique fonctionne."""
    assert validate_semantic("Paris is the capital of France.", "The capital of France is Paris.") is True


def test_validate_semantic_rejects_a_real_unrelated_answer():
    assert validate_semantic("Bananas are yellow.", "The capital of France is Paris.") is False


def test_validate_semantic_is_honestly_false_for_an_empty_answer():
    """Validation criterion: robustesse -- réponse vide."""
    assert validate_semantic("", "The capital of France is Paris.") is False


# --------------------------------------- validate_fuzzy --


def test_validate_fuzzy_accepts_a_real_near_typo_answer():
    """Validation criterion: la validation floue fonctionne."""
    assert validate_fuzzy("Pari", "Paris") is True


def test_validate_fuzzy_rejects_a_real_very_different_answer():
    assert validate_fuzzy("London", "Paris") is False


def test_validate_fuzzy_honors_a_real_explicit_threshold():
    assert validate_fuzzy("Pariz", "Paris", threshold=0.99) is False
    assert validate_fuzzy("Pariz", "Paris", threshold=0.5) is True


# --------------------------------------- set_ground_truth / get_ground_truth --


async def test_set_ground_truth_persists_the_real_answer(db_session):
    """Validation criterion: la définition de ground truth fonctionne."""
    org = await _make_org(db_session, "Ground Truth Org")
    question = await _make_question(db_session, org.id)

    await set_ground_truth(db_session, question.id, "Paris", answer_type="exact")
    await db_session.commit()

    ground_truth = await get_ground_truth(db_session, question.id)
    assert ground_truth == {"expected_answer": "Paris", "expected_answer_type": "exact", "expected_answer_metadata": None}


async def test_set_ground_truth_rejects_a_real_unknown_answer_type(db_session):
    org = await _make_org(db_session, "Ground Truth Org 2")
    question = await _make_question(db_session, org.id)
    with pytest.raises(ValueError):
        await set_ground_truth(db_session, question.id, "Paris", answer_type="not_a_real_type")


async def test_get_ground_truth_is_honestly_none_without_a_real_answer_set(db_session):
    org = await _make_org(db_session, "Ground Truth Org 3")
    question = await _make_question(db_session, org.id)
    assert await get_ground_truth(db_session, question.id) is None


async def test_set_ground_truth_enforces_the_real_max_answers_cap(db_session, monkeypatch):
    monkeypatch.setattr(settings, "GROUND_TRUTH_MAX_ANSWERS", 1)
    org = await _make_org(db_session, "Ground Truth Cap Org")
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    q1 = EvaluationQuestion(dataset_id=dataset.id, question="Q1?")
    q2 = EvaluationQuestion(dataset_id=dataset.id, question="Q2?")
    db_session.add_all([q1, q2])
    await db_session.commit()

    await set_ground_truth(db_session, q1.id, "A1")
    await db_session.commit()
    with pytest.raises(ValueError):
        await set_ground_truth(db_session, q2.id, "A2")


# --------------------------------------- validate_answer --


async def test_validate_answer_uses_the_real_configured_method(db_session):
    org = await _make_org(db_session, "Validate Answer Org")
    question = await _make_question(db_session, org.id)
    await set_ground_truth(db_session, question.id, "Paris", answer_type="contains")
    await db_session.commit()

    assert await validate_answer(db_session, question.id, "The capital is Paris.") is True


async def test_validate_answer_is_honestly_false_without_a_real_ground_truth(db_session):
    org = await _make_org(db_session, "Validate Answer Org 2")
    question = await _make_question(db_session, org.id)
    assert await validate_answer(db_session, question.id, "Any answer") is False
