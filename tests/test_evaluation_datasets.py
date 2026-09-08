"""Partie 7.1.1 -- dataset manager. Fast SQLite suite."""

import json
import uuid

from api.models.organization import Organization
from api.services.evaluation_datasets import (
    add_question, create_dataset, delete_dataset, delete_question, export_questions, get_dataset, get_questions,
    import_questions, list_datasets, update_dataset, update_question,
)


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


# --------------------------------------- create/get/update/delete_dataset --


async def test_create_dataset_persists_a_real_row(db_session):
    """Validation criterion: la création de dataset fonctionne."""
    org = await _make_org(db_session, "Dataset Org")
    await db_session.commit()
    dataset = await create_dataset(db_session, org.id, "My Dataset", "A real description")
    await db_session.commit()

    fetched = await get_dataset(db_session, dataset.id)
    assert fetched is not None
    assert fetched.name == "My Dataset"
    assert fetched.version == 1
    assert fetched.is_active is True


async def test_update_dataset_changes_only_the_real_given_fields(db_session):
    org = await _make_org(db_session, "Dataset Update Org")
    await db_session.commit()
    dataset = await create_dataset(db_session, org.id, "Original", "Original desc")
    await db_session.commit()

    updated = await update_dataset(db_session, dataset.id, name="Renamed")
    await db_session.commit()
    assert updated.name == "Renamed"
    assert updated.description == "Original desc"


async def test_delete_dataset_is_a_real_soft_delete(db_session):
    """Validation criterion: robustesse -- suppression douce."""
    org = await _make_org(db_session, "Dataset Delete Org")
    await db_session.commit()
    dataset = await create_dataset(db_session, org.id, "To Delete")
    await db_session.commit()

    assert await delete_dataset(db_session, dataset.id) is True
    await db_session.commit()
    assert await get_dataset(db_session, dataset.id) is None


async def test_delete_dataset_is_honestly_false_for_an_unknown_dataset(db_session):
    assert await delete_dataset(db_session, uuid.uuid4()) is False


# --------------------------------------- list_datasets --


async def test_list_datasets_is_isolated_by_real_organization(db_session):
    """Validation criterion: les datasets sont isolés par organisation."""
    org_a = await _make_org(db_session, "Dataset Isolation Org A")
    org_b = await _make_org(db_session, "Dataset Isolation Org B")
    await db_session.commit()
    await create_dataset(db_session, org_a.id, "A's Dataset")
    await create_dataset(db_session, org_b.id, "B's Dataset")
    await db_session.commit()

    result = await list_datasets(db_session, org_a.id)
    assert result["total"] == 1
    assert result["items"][0].name == "A's Dataset"


async def test_list_datasets_excludes_real_soft_deleted_datasets(db_session):
    org = await _make_org(db_session, "Dataset List Org")
    await db_session.commit()
    dataset = await create_dataset(db_session, org.id, "Will be deleted")
    await db_session.commit()
    await delete_dataset(db_session, dataset.id)
    await db_session.commit()

    result = await list_datasets(db_session, org.id)
    assert result["total"] == 0


# --------------------------------------- add/update/delete_question / get_questions --


async def test_add_question_auto_detects_real_difficulty(db_session):
    """Validation criterion: l'ajout de questions fonctionne."""
    org = await _make_org(db_session, "Question Org")
    await db_session.commit()
    dataset = await create_dataset(db_session, org.id, "Q Dataset")
    await db_session.commit()

    question = await add_question(db_session, dataset.id, "What is the capital of France?")
    await db_session.commit()
    assert question.difficulty in ("easy", "medium", "hard")


async def test_update_question_changes_real_fields(db_session):
    org = await _make_org(db_session, "Question Update Org")
    await db_session.commit()
    dataset = await create_dataset(db_session, org.id, "Q Dataset")
    await db_session.commit()
    question = await add_question(db_session, dataset.id, "Original question?")
    await db_session.commit()

    updated = await update_question(db_session, question.id, {"question": "Updated question?"})
    await db_session.commit()
    assert updated.question == "Updated question?"


async def test_delete_question_removes_the_real_row(db_session):
    org = await _make_org(db_session, "Question Delete Org")
    await db_session.commit()
    dataset = await create_dataset(db_session, org.id, "Q Dataset")
    await db_session.commit()
    question = await add_question(db_session, dataset.id, "Delete me?")
    await db_session.commit()

    assert await delete_question(db_session, question.id) is True
    await db_session.commit()
    result = await get_questions(db_session, dataset.id)
    assert result["total"] == 0


async def test_get_questions_filters_by_real_difficulty(db_session):
    org = await _make_org(db_session, "Question Filter Org")
    await db_session.commit()
    dataset = await create_dataset(db_session, org.id, "Q Dataset")
    await db_session.commit()
    await add_question(db_session, dataset.id, "Easy?", difficulty="easy")
    await add_question(db_session, dataset.id, "Hard?", difficulty="hard")
    await db_session.commit()

    result = await get_questions(db_session, dataset.id, filters={"difficulty": "easy"})
    assert result["total"] == 1


# --------------------------------------- import_questions / export_questions --


async def test_import_questions_from_real_json(db_session):
    """Validation criterion: l'import/export fonctionne (JSON)."""
    org = await _make_org(db_session, "Import Org")
    await db_session.commit()
    dataset = await create_dataset(db_session, org.id, "Import Dataset")
    await db_session.commit()

    content = json.dumps([
        {"question": "Q1?", "expected_answer": "A1", "difficulty": "easy"},
        {"question": "Q2?", "expected_answer": "A2"},
    ]).encode("utf-8")
    result = await import_questions(db_session, dataset.id, content, format="json")
    await db_session.commit()

    assert result["imported"] == 2
    assert result["errors"] == []
    listed = await get_questions(db_session, dataset.id)
    assert listed["total"] == 2


async def test_import_questions_skips_real_rows_missing_a_question(db_session):
    """Validation criterion: robustesse -- lignes invalides ignorées, pas d'échec total."""
    org = await _make_org(db_session, "Import Errors Org")
    await db_session.commit()
    dataset = await create_dataset(db_session, org.id, "Import Errors Dataset")
    await db_session.commit()

    content = json.dumps([{"expected_answer": "no question here"}, {"question": "Real question?"}]).encode("utf-8")
    result = await import_questions(db_session, dataset.id, content, format="json")
    await db_session.commit()

    assert result["imported"] == 1
    assert len(result["errors"]) == 1


async def test_import_questions_from_real_csv(db_session):
    org = await _make_org(db_session, "Import CSV Org")
    await db_session.commit()
    dataset = await create_dataset(db_session, org.id, "Import CSV Dataset")
    await db_session.commit()

    content = b"question,expected_answer,difficulty,category\nWhat is 2+2?,4,easy,math\n"
    result = await import_questions(db_session, dataset.id, content, format="csv")
    await db_session.commit()
    assert result["imported"] == 1


async def test_export_questions_round_trips_through_real_json(db_session):
    org = await _make_org(db_session, "Export Org")
    await db_session.commit()
    dataset = await create_dataset(db_session, org.id, "Export Dataset")
    await db_session.commit()
    await add_question(db_session, dataset.id, "Exportable question?", expected_answer="An answer")
    await db_session.commit()

    exported = await export_questions(db_session, dataset.id, format="json")
    parsed = json.loads(exported)
    assert len(parsed) == 1
    assert parsed[0]["question"] == "Exportable question?"


async def test_export_questions_as_real_csv(db_session):
    org = await _make_org(db_session, "Export CSV Org")
    await db_session.commit()
    dataset = await create_dataset(db_session, org.id, "Export CSV Dataset")
    await db_session.commit()
    await add_question(db_session, dataset.id, "Exportable question?")
    await db_session.commit()

    exported = await export_questions(db_session, dataset.id, format="csv")
    assert "Exportable question?" in exported
