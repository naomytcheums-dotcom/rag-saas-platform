"""Parties 7.2.1/7.2.2/7.2.3/7.2.4/7.2.5/7.2.6/7.2.7 -- retrieval metrics. Fast SQLite suite."""

import uuid

import pytest

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion, EvaluationResult
from api.models.organization import Organization
from api.services.ground_truth_documents import calculate_dcg, calculate_idcg
from api.services.retrieval_metrics import (
    calculate_mrr, calculate_ndcg, calculate_precision, calculate_recall_at_1, calculate_recall_at_3,
    calculate_recall_at_5, calculate_recall_at_10, get_mrr_summary, get_ndcg_summary, get_precision_summary,
    get_recall_summary,
)


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_question(db_session, dataset_id, question="Q?"):
    row = EvaluationQuestion(dataset_id=dataset_id, question=question)
    db_session.add(row)
    await db_session.flush()
    return row


async def _make_result(db_session, question_id, metrics):
    result = EvaluationResult(
        question_id=question_id, model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
        actual_answer="a", metrics=metrics, latency_ms=100,
    )
    db_session.add(result)
    await db_session.flush()
    return result


_EXPECTED = [{"document_id": "A"}]


# --------------------------------------- calculate_recall_at_1/3/5/10 --


def test_calculate_recall_at_1_is_the_real_recall_at_k_1():
    """Validation criterion: le calcul de Recall@1 fonctionne (précision)."""
    assert calculate_recall_at_1(["A", "B"], _EXPECTED) == 1.0
    assert calculate_recall_at_1(["B", "A"], _EXPECTED) == 0.0


def test_calculate_recall_at_3_is_coherent_with_recall_at_1():
    """Validation criterion: cohérence -- Recall@3 >= Recall@1."""
    retrieved = ["B", "A", "C"]
    assert calculate_recall_at_1(retrieved, _EXPECTED) == 0.0
    assert calculate_recall_at_3(retrieved, _EXPECTED) == 1.0


def test_calculate_recall_at_5_is_coherent_with_recall_at_1_and_3():
    """Validation criterion: cohérence -- Recall@5 >= Recall@3 >= Recall@1."""
    retrieved = ["X", "Y", "Z", "W", "A"]
    assert calculate_recall_at_1(retrieved, _EXPECTED) == 0.0
    assert calculate_recall_at_3(retrieved, _EXPECTED) == 0.0
    assert calculate_recall_at_5(retrieved, _EXPECTED) == 1.0


def test_calculate_recall_at_10_is_coherent_with_smaller_k():
    """Validation criterion: cohérence -- Recall@10 >= Recall@5 >= @3 >= @1."""
    retrieved = ["X"] * 9 + ["A"]
    assert calculate_recall_at_5(retrieved, _EXPECTED) == 0.0
    assert calculate_recall_at_10(retrieved, _EXPECTED) == 1.0


def test_calculate_recall_at_k_is_honest_with_fewer_real_documents_retrieved():
    """Validation criterion: robustesse -- moins de k documents récupérés."""
    assert calculate_recall_at_10(["A"], _EXPECTED) == 1.0
    assert calculate_recall_at_10(["B"], _EXPECTED) == 0.0
    assert calculate_recall_at_3(["A"], _EXPECTED) == 1.0


def test_calculate_recall_at_1_is_honestly_zero_without_real_documents_retrieved():
    """Validation criterion: robustesse -- aucun document récupéré."""
    assert calculate_recall_at_1([], _EXPECTED) == 0.0


# --------------------------------------- calculate_mrr --


def test_calculate_mrr_matches_the_real_ground_truth_documents_definition():
    """Validation criterion: le MRR est correctement calculé."""
    assert calculate_mrr(["X", "A"], _EXPECTED) == 0.5


def test_calculate_mrr_is_honestly_zero_without_a_real_relevant_document():
    """Validation criterion: robustesse -- aucun document pertinent trouvé."""
    assert calculate_mrr(["X", "Y"], _EXPECTED) == 0.0


# --------------------------------------- calculate_dcg/idcg/ndcg --


def test_calculate_dcg_and_idcg_are_real_and_public():
    """Validation criterion: le calcul de DCG fonctionne / IDCG fonctionne."""
    expected = [{"document_id": "A", "relevance_score": 3}, {"document_id": "B", "relevance_score": 1}]
    dcg = calculate_dcg(["A", "B"], expected, k=2)
    idcg = calculate_idcg(expected, k=2)
    assert dcg == idcg  # ideal order


def test_calculate_ndcg_uses_the_real_exponential_gain_by_default():
    """Validation criterion: le NDCG est correctement calculé (pertinence graduée)."""
    expected = [{"document_id": "A", "relevance_score": 3}, {"document_id": "B", "relevance_score": 1}]
    assert calculate_ndcg(["A", "B"], expected, k=2) == pytest.approx(1.0)
    assert calculate_ndcg(["B", "A"], expected, k=2) < 1.0


def test_calculate_ndcg_honors_real_graded_relevance_toggle(monkeypatch):
    """Validation criterion: les tests couvrent la pertinence graduée."""
    monkeypatch.setattr(settings, "NDCG_GRADED_RELEVANCE", False)
    expected = [{"document_id": "A", "relevance_score": 3}, {"document_id": "B", "relevance_score": 1}]
    # With graded relevance disabled, every real expected doc counts as
    # relevance 1.0 -- both real orders become equally, perfectly ideal.
    assert calculate_ndcg(["A", "B"], expected, k=2) == pytest.approx(1.0)
    assert calculate_ndcg(["B", "A"], expected, k=2) == pytest.approx(1.0)


def test_calculate_ndcg_is_honestly_zero_without_real_documents_retrieved():
    """Validation criterion: robustesse -- aucun document récupéré."""
    expected = [{"document_id": "A", "relevance_score": 1}]
    assert calculate_ndcg([], expected) == 0.0


# --------------------------------------- calculate_precision --


def test_calculate_precision_uses_the_real_default_k():
    """Validation criterion: la Precision est correctement calculée."""
    assert calculate_precision(["A", "B", "C", "D", "E"], _EXPECTED) == 1 / settings.PRECISION_DEFAULT_K


def test_calculate_precision_honors_a_real_explicit_k():
    assert calculate_precision(["A", "B"], _EXPECTED, k=2) == 0.5


def test_calculate_precision_is_honestly_zero_without_real_documents_retrieved():
    """Validation criterion: robustesse -- aucun document récupéré."""
    assert calculate_precision([], _EXPECTED) == 0.0


# --------------------------------------- summaries --


async def test_get_recall_summary_averages_the_real_stored_metric(db_session):
    org = await _make_org(db_session, "Recall Summary Org")
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    q1 = await _make_question(db_session, dataset.id)
    q2 = await _make_question(db_session, dataset.id)
    await _make_result(db_session, q1.id, {"recall_at_1": 1.0})
    await _make_result(db_session, q2.id, {"recall_at_1": 0.0})
    await db_session.commit()

    summary = await get_recall_summary(db_session, dataset.id, k=1)
    assert summary == {"metric": "recall_at_1", "count": 2, "average": 0.5, "min": 0.0, "max": 1.0}


async def test_get_mrr_summary_is_honest_with_no_real_results(db_session):
    """Validation criterion: robustesse -- aucun résultat."""
    org = await _make_org(db_session, "MRR Summary Org")
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.commit()

    summary = await get_mrr_summary(db_session, dataset.id)
    assert summary == {"metric": "mrr", "count": 0, "average": None, "min": None, "max": None}


async def test_get_ndcg_summary_uses_the_real_default_k(db_session):
    org = await _make_org(db_session, "NDCG Summary Org")
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    q1 = await _make_question(db_session, dataset.id)
    await _make_result(db_session, q1.id, {f"ndcg_at_{settings.NDCG_DEFAULT_K}": 0.8})
    await db_session.commit()

    summary = await get_ndcg_summary(db_session, dataset.id)
    assert summary["average"] == 0.8


async def test_get_precision_summary_uses_the_real_default_k(db_session):
    org = await _make_org(db_session, "Precision Summary Org")
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    q1 = await _make_question(db_session, dataset.id)
    await _make_result(db_session, q1.id, {f"precision_at_{settings.PRECISION_DEFAULT_K}": 0.6})
    await db_session.commit()

    summary = await get_precision_summary(db_session, dataset.id)
    assert summary["average"] == 0.6
