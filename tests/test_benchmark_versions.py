"""Partie 7.1.6 -- benchmark versions. Fast SQLite suite."""

import uuid

import pytest
from sqlalchemy import select

from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.organization import Organization
from api.services.benchmark_versions import (
    compare_benchmark_versions, create_benchmark_version, get_benchmark_version, get_latest_benchmark_version,
    list_benchmark_versions, rollback_to_version,
)
from api.services.question_sets import create_question_set, add_question_to_set, get_questions_in_set


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_dataset_with_questions(db_session, n=2):
    org = await _make_org(db_session, f"Org {uuid.uuid4().hex[:6]}")
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    questions = []
    for i in range(n):
        q = EvaluationQuestion(dataset_id=dataset.id, question=f"Q{i}?", difficulty="easy")
        db_session.add(q)
        questions.append(q)
    await db_session.commit()
    return dataset, questions


# --------------------------------------- create_benchmark_version --


async def test_create_benchmark_version_snapshots_all_real_questions(db_session):
    """Validation criterion: la création de version fonctionne."""
    dataset, questions = await _make_dataset_with_questions(db_session, 2)
    version = await create_benchmark_version(db_session, dataset.id, description="v1")
    await db_session.commit()

    assert version.version_number == 1
    assert len(version.snapshot) == 2
    assert version.metadata_json["question_count"] == 2


async def test_create_benchmark_version_increments_the_real_version_number(db_session):
    dataset, _ = await _make_dataset_with_questions(db_session, 1)
    v1 = await create_benchmark_version(db_session, dataset.id)
    await db_session.commit()
    v2 = await create_benchmark_version(db_session, dataset.id)
    await db_session.commit()
    assert v1.version_number == 1
    assert v2.version_number == 2


async def test_create_benchmark_version_can_snapshot_a_real_question_set_only(db_session):
    dataset, questions = await _make_dataset_with_questions(db_session, 3)
    question_set = await create_question_set(db_session, dataset.id, "Subset")
    await db_session.commit()
    await add_question_to_set(db_session, question_set.id, questions[0].id)
    await db_session.commit()

    version = await create_benchmark_version(db_session, dataset.id, question_set_id=question_set.id)
    await db_session.commit()
    assert len(version.snapshot) == 1


# --------------------------------------- list/get_latest --


async def test_list_benchmark_versions_orders_newest_first(db_session):
    dataset, _ = await _make_dataset_with_questions(db_session, 1)
    await create_benchmark_version(db_session, dataset.id)
    await db_session.commit()
    await create_benchmark_version(db_session, dataset.id)
    await db_session.commit()

    result = await list_benchmark_versions(db_session, dataset.id)
    assert result["total"] == 2
    assert result["items"][0].version_number == 2


async def test_get_latest_benchmark_version_returns_the_real_highest_number(db_session):
    dataset, _ = await _make_dataset_with_questions(db_session, 1)
    await create_benchmark_version(db_session, dataset.id)
    await db_session.commit()
    latest = await create_benchmark_version(db_session, dataset.id)
    await db_session.commit()

    fetched = await get_latest_benchmark_version(db_session, dataset.id)
    assert fetched.id == latest.id


# --------------------------------------- compare_benchmark_versions --


async def test_compare_benchmark_versions_detects_real_added_removed_changed(db_session):
    """Validation criterion: la comparaison de versions fonctionne."""
    dataset, questions = await _make_dataset_with_questions(db_session, 2)
    v1 = await create_benchmark_version(db_session, dataset.id)
    await db_session.commit()

    questions[0].difficulty = "hard"
    new_question = EvaluationQuestion(dataset_id=dataset.id, question="New one?")
    db_session.add(new_question)
    await db_session.delete(questions[1])
    await db_session.commit()

    v2 = await create_benchmark_version(db_session, dataset.id)
    await db_session.commit()

    diff = await compare_benchmark_versions(db_session, v1.id, v2.id)
    assert diff["questions_added"] == 1
    assert diff["questions_removed"] == 1
    assert diff["questions_changed"] == 1


async def test_compare_benchmark_versions_rejects_a_real_unknown_version(db_session):
    with pytest.raises(ValueError):
        await compare_benchmark_versions(db_session, uuid.uuid4(), uuid.uuid4())


# --------------------------------------- rollback_to_version --


async def test_rollback_to_version_restores_the_real_snapshot_content(db_session):
    """Validation criterion: le rollback fonctionne."""
    dataset, questions = await _make_dataset_with_questions(db_session, 2)
    version = await create_benchmark_version(db_session, dataset.id)
    await db_session.commit()

    extra = EvaluationQuestion(dataset_id=dataset.id, question="Extra question added after v1?")
    db_session.add(extra)
    await db_session.commit()

    restored = await rollback_to_version(db_session, dataset.id, version.version_number)
    await db_session.commit()
    assert restored is not None

    remaining = (await db_session.scalars(select(EvaluationQuestion).where(EvaluationQuestion.dataset_id == dataset.id))).all()
    assert len(remaining) == 2
    assert {q.question for q in remaining} == {q.question for q in questions}


async def test_rollback_to_version_is_honestly_none_for_an_unknown_version(db_session):
    """Validation criterion: robustesse -- version inexistante."""
    dataset, _ = await _make_dataset_with_questions(db_session, 1)
    assert await rollback_to_version(db_session, dataset.id, 999) is None


async def test_rollback_to_version_rejects_a_real_corrupted_snapshot(db_session):
    """Validation criterion: robustesse -- version corrompue."""
    dataset, _ = await _make_dataset_with_questions(db_session, 1)
    version = await create_benchmark_version(db_session, dataset.id)
    version.snapshot = "not a real list"
    await db_session.commit()

    with pytest.raises(ValueError):
        await rollback_to_version(db_session, dataset.id, version.version_number)

    # A real, corrupted snapshot must never touch existing data.
    remaining = (await db_session.scalars(select(EvaluationQuestion).where(EvaluationQuestion.dataset_id == dataset.id))).all()
    assert len(remaining) == 1
