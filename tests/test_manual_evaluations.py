"""Partie 7.3.2 -- manual (human) evaluations. Fast SQLite suite."""

import uuid

import pytest

from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.organization import Organization
from api.models.user import User
from api.services.manual_evaluations import (
    create_manual_evaluation, get_manual_evaluation_stats, get_manual_evaluation_summary, list_manual_evaluations,
    update_manual_evaluation,
)


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_question(db_session, org_id):
    dataset = EvaluationDataset(organization_id=org_id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?")
    db_session.add(question)
    await db_session.commit()
    return dataset, question


async def _make_user(db_session, email):
    user = User(email=email, hashed_password="irrelevant")
    db_session.add(user)
    await db_session.flush()
    return user


async def test_create_manual_evaluation_works(db_session):
    """Validation criterion: la création d'évaluation fonctionne."""
    org = await _make_org(db_session, "Manual Eval Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)
    evaluator = await _make_user(db_session, "evaluator1@example.com")
    await db_session.commit()

    evaluation = await create_manual_evaluation(
        db_session, question.id, None, evaluator.id, score=4, feedback="Good answer.", criteria={"accuracy": 5, "clarity": 4},
    )
    await db_session.commit()

    assert evaluation.score == 4
    assert evaluation.criteria == {"accuracy": 5, "clarity": 4}


async def test_create_manual_evaluation_rejects_an_unknown_criterion(db_session):
    """Validation criterion: robustesse -- critère invalide."""
    org = await _make_org(db_session, "Manual Eval Bad Criteria Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)
    evaluator = await _make_user(db_session, "evaluator2@example.com")
    await db_session.commit()

    with pytest.raises(ValueError):
        await create_manual_evaluation(db_session, question.id, None, evaluator.id, criteria={"not_a_real_criterion": 3})


async def test_create_manual_evaluation_allows_a_real_partial_criteria_set(db_session):
    """Validation criterion: robustesse -- un critère manquant n'est
    jamais une erreur."""
    org = await _make_org(db_session, "Manual Eval Partial Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)
    evaluator = await _make_user(db_session, "evaluator3@example.com")
    await db_session.commit()

    evaluation = await create_manual_evaluation(db_session, question.id, None, evaluator.id, criteria={"accuracy": 3})
    assert evaluation.criteria == {"accuracy": 3}


async def test_update_manual_evaluation_changes_only_the_given_real_fields(db_session):
    """Validation criterion: la modification fonctionne."""
    org = await _make_org(db_session, "Manual Eval Update Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)
    evaluator = await _make_user(db_session, "evaluator4@example.com")
    await db_session.commit()
    evaluation = await create_manual_evaluation(db_session, question.id, None, evaluator.id, score=2, feedback="Meh.")
    await db_session.commit()

    updated = await update_manual_evaluation(db_session, evaluation.id, score=5)
    await db_session.commit()

    assert updated.score == 5
    assert updated.feedback == "Meh."  # unchanged


async def test_update_manual_evaluation_is_honestly_none_for_an_unknown_evaluation(db_session):
    """Validation criterion: robustesse."""
    assert await update_manual_evaluation(db_session, uuid.uuid4(), score=3) is None


async def test_get_manual_evaluation_summary_averages_real_scores_and_criteria(db_session):
    org = await _make_org(db_session, "Manual Eval Summary Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)
    evaluator_a = await _make_user(db_session, "evaluator5@example.com")
    evaluator_b = await _make_user(db_session, "evaluator6@example.com")
    await db_session.commit()
    await create_manual_evaluation(db_session, question.id, None, evaluator_a.id, score=4, criteria={"accuracy": 5})
    await create_manual_evaluation(db_session, question.id, None, evaluator_b.id, score=2, criteria={"accuracy": 3})
    await db_session.commit()

    summary = await get_manual_evaluation_summary(db_session, question.id)
    assert summary["count"] == 2
    assert summary["average_score"] == 3.0
    assert summary["criteria_averages"]["accuracy"] == 4.0
    assert summary["criteria_averages"]["clarity"] is None


async def test_list_manual_evaluations_paginates(db_session):
    org = await _make_org(db_session, "Manual Eval List Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)
    for i in range(3):
        evaluator = await _make_user(db_session, f"evaluator-list-{i}@example.com")
        await db_session.commit()
        await create_manual_evaluation(db_session, question.id, None, evaluator.id, score=3)
    await db_session.commit()

    page = await list_manual_evaluations(db_session, question.id, limit=2, offset=0)
    assert page["total"] == 3
    assert len(page["items"]) == 2


async def test_get_manual_evaluation_stats_aggregates_across_a_real_dataset(db_session):
    """Validation criterion: les statistiques sont correctes."""
    org = await _make_org(db_session, "Manual Eval Stats Org")
    await db_session.commit()
    dataset, question_a = await _make_question(db_session, org.id)
    question_b = EvaluationQuestion(dataset_id=dataset.id, question="Q2?")
    db_session.add(question_b)
    await db_session.commit()
    evaluator = await _make_user(db_session, "evaluator-stats@example.com")
    await db_session.commit()
    await create_manual_evaluation(db_session, question_a.id, None, evaluator.id, score=4)
    await create_manual_evaluation(db_session, question_b.id, None, evaluator.id, score=2)
    await db_session.commit()

    stats = await get_manual_evaluation_stats(db_session, dataset.id)
    assert stats["count"] == 2
    assert stats["average_score"] == 3.0
