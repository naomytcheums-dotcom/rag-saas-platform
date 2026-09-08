"""Partie 7.1.2 -- question sets. Fast SQLite suite."""

import uuid

import pytest

from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.organization import Organization
from api.services.question_sets import (
    add_question_to_set, create_question_set, delete_question_set, duplicate_question_set, get_question_set,
    get_questions_in_set, list_question_sets, remove_question_from_set, reorder_questions, update_question_set,
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


async def _make_question(db_session, dataset_id, question="Q?"):
    row = EvaluationQuestion(dataset_id=dataset_id, question=question)
    db_session.add(row)
    await db_session.flush()
    return row


async def _make_setup(db_session, n_questions=3):
    org = await _make_org(db_session, f"Org {uuid.uuid4().hex[:6]}")
    dataset = await _make_dataset(db_session, org.id)
    questions = [await _make_question(db_session, dataset.id, f"Q{i}?") for i in range(n_questions)]
    await db_session.commit()
    return dataset, questions


# --------------------------------------- create/update/delete/get/list --


async def test_create_question_set_persists_a_real_row(db_session):
    """Validation criterion: la création d'ensemble fonctionne."""
    dataset, _ = await _make_setup(db_session, 0)
    question_set = await create_question_set(db_session, dataset.id, "My Set", "desc")
    await db_session.commit()

    fetched = await get_question_set(db_session, question_set.id)
    assert fetched.name == "My Set"
    assert fetched.dataset_id == dataset.id


async def test_update_question_set_changes_real_fields(db_session):
    dataset, _ = await _make_setup(db_session, 0)
    question_set = await create_question_set(db_session, dataset.id, "Original")
    await db_session.commit()

    updated = await update_question_set(db_session, question_set.id, name="Renamed")
    await db_session.commit()
    assert updated.name == "Renamed"


async def test_delete_question_set_removes_the_real_row(db_session):
    dataset, _ = await _make_setup(db_session, 0)
    question_set = await create_question_set(db_session, dataset.id, "To Delete")
    await db_session.commit()

    assert await delete_question_set(db_session, question_set.id) is True
    await db_session.commit()
    assert await get_question_set(db_session, question_set.id) is None


async def test_list_question_sets_is_scoped_to_the_real_dataset(db_session):
    dataset, _ = await _make_setup(db_session, 0)
    await create_question_set(db_session, dataset.id, "Set A")
    await db_session.commit()

    result = await list_question_sets(db_session, dataset.id)
    assert result["total"] == 1


# --------------------------------------- add/remove/get_questions_in_set --


async def test_add_question_to_set_appends_at_the_real_end(db_session):
    """Validation criterion: l'ajout de questions fonctionne."""
    dataset, questions = await _make_setup(db_session, 3)
    question_set = await create_question_set(db_session, dataset.id, "Set")
    await db_session.commit()

    for question in questions:
        await add_question_to_set(db_session, question_set.id, question.id)
    await db_session.commit()

    ordered = await get_questions_in_set(db_session, question_set.id)
    assert [q.id for q in ordered] == [q.id for q in questions]


async def test_remove_question_from_set_removes_the_real_membership(db_session):
    dataset, questions = await _make_setup(db_session, 2)
    question_set = await create_question_set(db_session, dataset.id, "Set")
    await db_session.commit()
    for question in questions:
        await add_question_to_set(db_session, question_set.id, question.id)
    await db_session.commit()

    assert await remove_question_from_set(db_session, question_set.id, questions[0].id) is True
    await db_session.commit()
    remaining = await get_questions_in_set(db_session, question_set.id)
    assert len(remaining) == 1
    assert remaining[0].id == questions[1].id


async def test_get_questions_in_set_is_honestly_empty_for_no_real_membership(db_session):
    dataset, _ = await _make_setup(db_session, 0)
    question_set = await create_question_set(db_session, dataset.id, "Empty Set")
    await db_session.commit()
    assert await get_questions_in_set(db_session, question_set.id) == []


# --------------------------------------- reorder_questions --


async def test_reorder_questions_applies_the_real_new_order(db_session):
    """Validation criterion: la réorganisation fonctionne."""
    dataset, questions = await _make_setup(db_session, 3)
    question_set = await create_question_set(db_session, dataset.id, "Set")
    await db_session.commit()
    for question in questions:
        await add_question_to_set(db_session, question_set.id, question.id)
    await db_session.commit()

    new_order = [questions[2].id, questions[0].id, questions[1].id]
    await reorder_questions(db_session, question_set.id, new_order)
    await db_session.commit()

    ordered = await get_questions_in_set(db_session, question_set.id)
    assert [q.id for q in ordered] == new_order


async def test_reorder_questions_rejects_a_real_mismatched_id_list(db_session):
    """Validation criterion: robustesse -- liste de réorganisation invalide."""
    dataset, questions = await _make_setup(db_session, 2)
    question_set = await create_question_set(db_session, dataset.id, "Set")
    await db_session.commit()
    for question in questions:
        await add_question_to_set(db_session, question_set.id, question.id)
    await db_session.commit()

    with pytest.raises(ValueError):
        await reorder_questions(db_session, question_set.id, [questions[0].id, uuid.uuid4()])


async def test_removing_a_real_question_cascades_out_of_its_real_sets(db_session):
    """Validation criterion: robustesse -- une question supprimée disparaît des ensembles."""
    dataset, questions = await _make_setup(db_session, 2)
    question_set = await create_question_set(db_session, dataset.id, "Set")
    await db_session.commit()
    for question in questions:
        await add_question_to_set(db_session, question_set.id, question.id)
    await db_session.commit()

    await db_session.delete(questions[0])
    await db_session.commit()

    remaining = await get_questions_in_set(db_session, question_set.id)
    assert len(remaining) == 1
    assert remaining[0].id == questions[1].id


# --------------------------------------- duplicate_question_set --


async def test_duplicate_question_set_copies_real_membership(db_session):
    """Validation criterion: la duplication fonctionne."""
    dataset, questions = await _make_setup(db_session, 2)
    original = await create_question_set(db_session, dataset.id, "Original Set")
    await db_session.commit()
    for question in questions:
        await add_question_to_set(db_session, original.id, question.id)
    await db_session.commit()

    duplicate = await duplicate_question_set(db_session, original.id, "Copied Set")
    await db_session.commit()

    assert duplicate.name == "Copied Set"
    assert duplicate.id != original.id
    duplicate_questions = await get_questions_in_set(db_session, duplicate.id)
    assert [q.id for q in duplicate_questions] == [q.id for q in questions]
