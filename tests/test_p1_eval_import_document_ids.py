"""Eval Lab import: the ground-truth documents of a dataset must point to documents that exist (Lot E). A dataset with ids that match nothing
scores Recall/MRR/NDCG = 0 for every question without any error."""

import json
import uuid

from api.models.document import Document
from api.models.organization import Organization
from api.services.evaluation_datasets import create_dataset, import_questions, get_questions


async def _world(db_session):
    org = Organization(name="Eval Org", slug=f"eval-{uuid.uuid4().hex[:8]}")
    other = Organization(name="Other Org", slug=f"other-{uuid.uuid4().hex[:8]}")
    db_session.add_all([org, other])
    await db_session.flush()
    real = Document(organization_id=org.id, name="real.txt", file_key="k", file_size=1, file_type="text/plain", status="completed", created_by=uuid.uuid4())
    foreign = Document(organization_id=other.id, name="foreign.txt", file_key="k2", file_size=1, file_type="text/plain", status="completed", created_by=uuid.uuid4())
    db_session.add_all([real, foreign])
    await db_session.flush()
    dataset = await create_dataset(db_session, org.id, "d")
    await db_session.commit()
    return dataset.id, str(real.id), str(foreign.id)


def _payload(*docs_per_question):
    return json.dumps([{"question": f"q{n}", "expected_answer": "a", "expected_documents": docs} for n, docs in enumerate(docs_per_question)]).encode()


async def test_by_default_the_import_keeps_accepting_any_well_shaped_document_id(db_session):
    dataset_id, real, _foreign = await _world(db_session)
    result = await import_questions(db_session, dataset_id, _payload([{"document_id": str(uuid.uuid4())}]), "json")
    assert result == {"imported": 1, "errors": []}  # historical behaviour kept: existence is opt-in


async def test_a_badly_shaped_expected_document_is_always_skipped_and_reported(db_session):
    dataset_id, real, _foreign = await _world(db_session)
    result = await import_questions(db_session, dataset_id, _payload([{"relevance_score": 1}], "not-a-list", [{"document_id": real}]), "json")
    assert result["imported"] == 1
    assert any("document_id" in e for e in result["errors"]) and any("must be a list" in e for e in result["errors"])


async def test_with_verification_unknown_foreign_and_malformed_ids_are_skipped_and_reported(db_session):
    dataset_id, real, foreign = await _world(db_session)
    missing = str(uuid.uuid4())
    payload = _payload([{"document_id": real}], [{"document_id": missing}], [{"document_id": foreign}], [{"document_id": "not-a-uuid"}], [])
    result = await import_questions(db_session, dataset_id, payload, "json", verify_documents=True)
    await db_session.commit()
    assert result["imported"] == 2  # the real one, and the question with no expected document (e.g. unanswerable)
    assert len(result["errors"]) == 3 and all("does not exist in this organization" in e for e in result["errors"])
    page = await get_questions(db_session, dataset_id)
    assert page["total"] == 2 and sorted(q.question for q in page["items"]) == ["q0", "q4"]


async def test_a_soft_deleted_document_does_not_count_as_existing(db_session):
    import datetime as dt

    dataset_id, real, _foreign = await _world(db_session)
    document = await db_session.get(Document, uuid.UUID(real))
    document.deleted_at = dt.datetime.now(dt.timezone.utc)
    await db_session.commit()
    result = await import_questions(db_session, dataset_id, _payload([{"document_id": real}]), "json", verify_documents=True)
    assert result["imported"] == 0 and len(result["errors"]) == 1
