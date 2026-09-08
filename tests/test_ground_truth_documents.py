"""Partie 7.1.4 -- ground-truth documents. Fast SQLite suite (pure-Python metrics, DB for set/get)."""

import uuid

import pytest

from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.organization import Organization
from api.services.ground_truth_documents import (
    calculate_retrieval_hit_rate, calculate_retrieval_mrr, calculate_retrieval_ndcg, calculate_retrieval_precision,
    calculate_retrieval_recall, evaluate_retrieval, get_ground_truth_documents, set_ground_truth_documents,
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


_EXPECTED = [{"document_id": "A"}, {"document_id": "B"}]


# --------------------------------------- calculate_retrieval_precision / recall --


def test_calculate_retrieval_precision_counts_real_hits_in_top_k():
    """Validation criterion: precision@k."""
    assert calculate_retrieval_precision(["A", "X", "Y"], _EXPECTED, k=3) == 1 / 3


def test_calculate_retrieval_recall_counts_real_fraction_of_expected_found():
    """Validation criterion: recall@k."""
    assert calculate_retrieval_recall(["A", "X", "Y"], _EXPECTED, k=3) == 0.5


def test_calculate_retrieval_precision_is_honestly_zero_with_no_real_expected_documents():
    """Validation criterion: robustesse -- documents attendus vides."""
    assert calculate_retrieval_precision(["A"], []) == 0.0
    assert calculate_retrieval_recall(["A"], []) == 0.0


# --------------------------------------- calculate_retrieval_mrr --


def test_calculate_retrieval_mrr_is_the_real_reciprocal_of_the_first_hit_rank():
    """Validation criterion: mrr."""
    assert calculate_retrieval_mrr(["X", "A", "B"], _EXPECTED) == 1 / 2


def test_calculate_retrieval_mrr_is_honestly_zero_without_a_real_hit():
    assert calculate_retrieval_mrr(["X", "Y"], _EXPECTED) == 0.0


# --------------------------------------- calculate_retrieval_ndcg --


def test_calculate_retrieval_ndcg_is_perfect_for_the_real_ideal_order():
    """Validation criterion: ndcg@k."""
    expected = [{"document_id": "A", "relevance_score": 3}, {"document_id": "B", "relevance_score": 2}, {"document_id": "C", "relevance_score": 1}]
    assert calculate_retrieval_ndcg(["A", "B", "C"], expected, k=3) == pytest.approx(1.0)


def test_calculate_retrieval_ndcg_is_lower_for_a_real_worse_order():
    expected = [{"document_id": "A", "relevance_score": 3}, {"document_id": "B", "relevance_score": 2}, {"document_id": "C", "relevance_score": 1}]
    ideal = calculate_retrieval_ndcg(["A", "B", "C"], expected, k=3)
    worse = calculate_retrieval_ndcg(["C", "B", "A"], expected, k=3)
    assert worse < ideal


def test_calculate_retrieval_ndcg_is_honestly_zero_with_no_real_expected_documents():
    assert calculate_retrieval_ndcg(["A"], []) == 0.0


# --------------------------------------- calculate_retrieval_hit_rate --


def test_calculate_retrieval_hit_rate_is_real_and_binary():
    assert calculate_retrieval_hit_rate(["X", "A"], _EXPECTED, k=2) == 1.0
    assert calculate_retrieval_hit_rate(["X", "Y"], _EXPECTED, k=2) == 0.0


# --------------------------------------- set/get_ground_truth_documents --


async def test_set_ground_truth_documents_persists_the_real_list(db_session):
    """Validation criterion: la définition de documents attendus fonctionne."""
    org = await _make_org(db_session, "Ground Truth Docs Org")
    question = await _make_question(db_session, org.id)

    await set_ground_truth_documents(db_session, question.id, _EXPECTED)
    await db_session.commit()

    fetched = await get_ground_truth_documents(db_session, question.id)
    assert fetched == _EXPECTED


async def test_set_ground_truth_documents_rejects_a_real_malformed_entry(db_session):
    org = await _make_org(db_session, "Ground Truth Docs Org 2")
    question = await _make_question(db_session, org.id)
    with pytest.raises(ValueError):
        await set_ground_truth_documents(db_session, question.id, [{"no_document_id": "x"}])


async def test_get_ground_truth_documents_is_honestly_none_without_a_real_set(db_session):
    org = await _make_org(db_session, "Ground Truth Docs Org 3")
    question = await _make_question(db_session, org.id)
    assert await get_ground_truth_documents(db_session, question.id) is None


# --------------------------------------- evaluate_retrieval --


async def test_evaluate_retrieval_computes_every_real_configured_metric(db_session):
    """Validation criterion: l'évaluation de la récupération fonctionne."""
    org = await _make_org(db_session, "Evaluate Retrieval Org")
    question = await _make_question(db_session, org.id)
    await set_ground_truth_documents(db_session, question.id, _EXPECTED)
    await db_session.commit()

    result = await evaluate_retrieval(db_session, question.id, ["A", "X"])
    assert set(result) == {"precision", "recall", "mrr", "ndcg"}
    assert result["mrr"] == 1.0


async def test_evaluate_retrieval_is_honestly_zero_without_real_expected_documents(db_session):
    """Validation criterion: robustesse -- documents attendus vides."""
    org = await _make_org(db_session, "Evaluate Retrieval Org 2")
    question = await _make_question(db_session, org.id)
    result = await evaluate_retrieval(db_session, question.id, ["A"])
    assert all(v == 0.0 for v in result.values())
