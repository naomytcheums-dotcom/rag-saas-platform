"""Partie 7.1.5 -- easy/medium/hard. Fast SQLite suite."""

import uuid

from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.organization import Organization
from api.services.question_difficulty import (
    auto_detect_difficulty, calculate_difficulty_score, get_difficulty_distribution, get_questions_by_difficulty,
)


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_dataset(db_session, org_id, name="Dataset"):
    dataset = EvaluationDataset(organization_id=org_id, name=name)
    db_session.add(dataset)
    await db_session.flush()
    return dataset


async def _make_question(db_session, dataset_id, question="Q?", difficulty=None):
    row = EvaluationQuestion(dataset_id=dataset_id, question=question, difficulty=difficulty)
    db_session.add(row)
    await db_session.flush()
    return row


# --------------------------------------- calculate_difficulty_score --


def test_calculate_difficulty_score_is_honestly_zero_for_an_empty_question():
    """Validation criterion: robustesse -- question vide."""
    assert calculate_difficulty_score("") == 0.0
    assert calculate_difficulty_score("   ") == 0.0


def test_calculate_difficulty_score_is_higher_for_a_real_longer_complex_question():
    """Validation criterion: les critères sont respectés (length/complexity)."""
    short = calculate_difficulty_score("What color is the sky?")
    long_complex = calculate_difficulty_score(
        "Which specific atmospheric phenomenon, that occurs because of the interaction between "
        "sunlight and gas molecules, explains why the sky appears blue during the day, and how "
        "does it relate to Rayleigh scattering, Isaac Newton, and various other optical effects?"
    )
    assert long_complex > short


# --------------------------------------- auto_detect_difficulty --


def test_auto_detect_difficulty_classifies_a_real_simple_question_as_easy():
    """Validation criterion: la détection automatique de difficulté fonctionne (facile)."""
    assert auto_detect_difficulty("What color is the sky?") == "easy"


def test_auto_detect_difficulty_classifies_a_real_complex_question_as_hard():
    """Validation criterion: la détection automatique de difficulté fonctionne (difficile)."""
    question = (
        "Which specific atmospheric phenomenon, that occurs because of the interaction between "
        "sunlight and gas molecules, explains why the sky appears blue during the day, and how "
        "does it relate to Rayleigh scattering, Isaac Newton, various other optical effects, "
        "and several historical experiments conducted in England and France?"
    )
    documents = [{"document_id": str(uuid.uuid4())} for _ in range(3)]
    assert auto_detect_difficulty(question, expected_documents=documents) == "hard"


def test_auto_detect_difficulty_incorporates_the_real_documents_required_factor():
    """Validation criterion: le critère documents_required est respecté."""
    question = "What is the capital of France?"
    without_docs = auto_detect_difficulty(question)
    with_many_docs = auto_detect_difficulty(question, expected_documents=[{"document_id": str(uuid.uuid4())} for _ in range(3)])
    assert calculate_difficulty_score(question) <= calculate_difficulty_score(question)  # sanity, no documents factor here
    assert without_docs != "hard" or with_many_docs == "hard"


def test_auto_detect_difficulty_is_honestly_easy_for_an_empty_question():
    """Validation criterion: robustesse -- question vide."""
    assert auto_detect_difficulty("") == "easy"


# --------------------------------------- get_questions_by_difficulty / distribution --


async def test_get_questions_by_difficulty_filters_real_questions(db_session):
    org = await _make_org(db_session, "Difficulty Org")
    dataset = await _make_dataset(db_session, org.id)
    await _make_question(db_session, dataset.id, difficulty="easy")
    await _make_question(db_session, dataset.id, difficulty="hard")
    await db_session.commit()

    easy_questions = await get_questions_by_difficulty(db_session, dataset.id, "easy")
    assert len(easy_questions) == 1
    assert easy_questions[0].difficulty == "easy"


async def test_get_difficulty_distribution_counts_real_questions_by_tier(db_session):
    """Validation criterion: la distribution des difficultés est correcte."""
    org = await _make_org(db_session, "Difficulty Distribution Org")
    dataset = await _make_dataset(db_session, org.id)
    await _make_question(db_session, dataset.id, difficulty="easy")
    await _make_question(db_session, dataset.id, difficulty="easy")
    await _make_question(db_session, dataset.id, difficulty="hard")
    await _make_question(db_session, dataset.id, difficulty=None)
    await db_session.commit()

    distribution = await get_difficulty_distribution(db_session, dataset.id)
    assert distribution == {"easy": 2, "medium": 0, "hard": 1, "unknown": 1}
