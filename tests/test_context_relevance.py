"""Partie 7.2.10 -- context relevance. Fast SQLite suite (pure-Python
factors 1/3/4; factor 2 uses real embeddings, same as
tests/test_answer_quality_metrics.py)."""

import uuid

import pytest

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion, EvaluationResult
from api.models.organization import Organization
from api.services.context_relevance import calculate_context_relevance, get_context_relevance_summary


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


def test_calculate_context_relevance_is_high_for_a_real_on_topic_context():
    """Validation criterion: relevance élevée."""
    question = "Why is the sky blue?"
    context = "The sky is blue because of Rayleigh scattering of sunlight in the atmosphere."
    chunks = [{"content": context}]
    result = calculate_context_relevance(question, context, chunks)
    assert result["score"] > 0.2
    assert set(result["factors"]) == {"context_coverage", "chunk_relevance_avg", "redundancy_score", "information_density"}


def test_calculate_context_relevance_is_low_for_a_real_off_topic_context():
    """Validation criterion: relevance faible."""
    question = "Why is the sky blue?"
    off_topic = calculate_context_relevance(question, "Bananas are a good source of potassium.", [{"content": "Bananas are a good source of potassium."}])
    on_topic = calculate_context_relevance(question, "The sky is blue because of Rayleigh scattering.", [{"content": "The sky is blue because of Rayleigh scattering."}])
    assert off_topic["score"] < on_topic["score"]


def test_calculate_context_relevance_is_honestly_zero_with_no_real_context_at_all():
    """Validation criterion: robustesse -- contexte vide."""
    result = calculate_context_relevance("Why is the sky blue?", None, [])
    assert result["score"] == 0.0
    assert all(v == 0.0 for v in result["factors"].values())


def test_calculate_context_relevance_redundancy_score_detects_real_duplicate_chunks():
    chunks = [{"content": "The sky is blue due to Rayleigh scattering."}, {"content": "The sky is blue due to Rayleigh scattering."}]
    result = calculate_context_relevance("q", "context", chunks)
    assert result["factors"]["redundancy_score"] > 0.8


def test_calculate_context_relevance_redundancy_score_is_honestly_zero_with_one_chunk():
    result = calculate_context_relevance("q", "context", [{"content": "one chunk"}])
    assert result["factors"]["redundancy_score"] == 0.0


def test_calculate_context_relevance_information_density_prefers_real_diverse_text():
    diverse = calculate_context_relevance("q", "apple banana cherry date elderberry fig grape", [])
    repetitive = calculate_context_relevance("q", "apple apple apple apple apple apple apple", [])
    assert diverse["factors"]["information_density"] > repetitive["factors"]["information_density"]


def test_calculate_context_relevance_raises_honestly_when_the_llm_path_is_requested(monkeypatch):
    """Validation criterion: robustesse -- le drapeau LLM ne fait jamais silencieusement autre chose."""
    monkeypatch.setattr(settings, "CONTEXT_RELEVANCE_USE_LLM", True)
    with pytest.raises(NotImplementedError):
        calculate_context_relevance("q", "context", [{"content": "a real chunk"}])


async def test_get_context_relevance_summary_averages_the_real_stored_metric(db_session):
    org = await _make_org(db_session, "Context Relevance Summary Org")
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?")
    db_session.add(question)
    await db_session.flush()
    result = EvaluationResult(
        question_id=question.id, model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
        actual_answer="a", metrics={"context_relevance": 0.7}, latency_ms=10,
    )
    db_session.add(result)
    await db_session.commit()

    summary = await get_context_relevance_summary(db_session, dataset.id)
    assert summary["average"] == 0.7
