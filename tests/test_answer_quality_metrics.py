"""Parties 7.2.8/7.2.9 -- faithfulness and answer relevance for evaluation runs. Fast SQLite suite."""

import uuid

import pytest

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion, EvaluationResult
from api.models.organization import Organization
from api.services.answer_quality_metrics import calculate_answer_relevance, calculate_faithfulness, get_answer_relevance_summary, get_faithfulness_summary


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


# --------------------------------------- calculate_faithfulness --


def test_calculate_faithfulness_is_high_for_a_real_well_supported_answer():
    """Validation criterion: le calcul de Faithfulness fonctionne (élevé)."""
    answer = "The clinical study included exactly 500 participants total in 2020 and was published in a peer reviewed journal."
    citations = [{"text": answer}]
    result = calculate_faithfulness(answer, citations, context=answer)
    assert result["score"] > 0.5
    assert set(result["factors"]) == {"claim_support", "source_alignment", "context_usage", "hallucination_absence"}


def test_calculate_faithfulness_reflects_a_real_contradicting_citation():
    """Validation criterion: robustesse -- absence de citations vs citation contradictoire."""
    answer = "The clinical study included exactly 500 participants total in 2020 and was published in a peer reviewed journal."
    contradicting = [{"text": "The clinical study included exactly 800 participants total in 2020 and was published in a peer reviewed journal."}]
    result = calculate_faithfulness(answer, contradicting)
    assert result["factors"]["hallucination_absence"] == 0.0


def test_calculate_faithfulness_is_honestly_zero_without_a_real_answer():
    """Validation criterion: robustesse -- pas de citations / réponse vide."""
    result = calculate_faithfulness("", [])
    assert result["score"] == 0.0
    assert all(v == 0.0 for v in result["factors"].values())


def test_calculate_faithfulness_is_a_real_no_op_score_without_real_citations():
    result = calculate_faithfulness("Some real answer with a claim in it.", [])
    assert result["factors"]["claim_support"] == 0.0
    assert result["factors"]["source_alignment"] == 0.0


# --------------------------------------- calculate_answer_relevance --


def test_calculate_answer_relevance_is_high_for_a_real_on_topic_answer():
    """Validation criterion: le calcul de Answer relevance fonctionne (élevé)."""
    question = "Why is the sky blue?"
    answer = "The sky is blue because of Rayleigh scattering of sunlight in the atmosphere."
    result = calculate_answer_relevance(question, answer)
    assert result["score"] > 0.3
    assert set(result["factors"]) == {"question_coverage", "key_terms_presence", "semantic_similarity", "length_adequacy"}


def test_calculate_answer_relevance_is_low_for_a_real_off_topic_answer():
    """Validation criterion: robustesse -- pertinence faible."""
    question = "Why is the sky blue?"
    answer = "Bananas are a good source of potassium."
    on_topic = calculate_answer_relevance(question, "The sky is blue because of Rayleigh scattering.")
    off_topic = calculate_answer_relevance(question, answer)
    assert off_topic["score"] < on_topic["score"]


def test_calculate_answer_relevance_is_honestly_zero_for_an_empty_answer():
    """Validation criterion: robustesse -- réponse vide."""
    result = calculate_answer_relevance("Why is the sky blue?", "")
    assert result["score"] == 0.0


def test_calculate_answer_relevance_key_terms_presence_checks_real_entities():
    question = "What did Isaac Newton discover in England?"
    with_terms = calculate_answer_relevance(question, "Isaac Newton discovered gravity while living in England.")
    without_terms = calculate_answer_relevance(question, "Someone discovered something somewhere.")
    assert with_terms["factors"]["key_terms_presence"] > without_terms["factors"]["key_terms_presence"]


def test_calculate_answer_relevance_raises_honestly_when_the_llm_path_is_requested(monkeypatch):
    """Validation criterion: robustesse -- le drapeau LLM ne fait jamais silencieusement autre chose."""
    monkeypatch.setattr(settings, "ANSWER_RELEVANCE_USE_LLM", True)
    with pytest.raises(NotImplementedError):
        calculate_answer_relevance("A question?", "A real, substantive answer.")


# --------------------------------------- get_faithfulness_summary / get_answer_relevance_summary --


async def test_get_faithfulness_summary_averages_the_real_stored_metric(db_session):
    org = await _make_org(db_session, "Faithfulness Summary Org")
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?")
    db_session.add(question)
    await db_session.flush()
    result = EvaluationResult(
        question_id=question.id, model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
        actual_answer="a", metrics={"faithfulness": 0.8}, latency_ms=10,
    )
    db_session.add(result)
    await db_session.commit()

    summary = await get_faithfulness_summary(db_session, dataset.id)
    assert summary["average"] == 0.8


async def test_get_answer_relevance_summary_is_honest_with_no_real_results(db_session):
    """Validation criterion: robustesse."""
    org = await _make_org(db_session, "Answer Relevance Summary Org")
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.commit()

    summary = await get_answer_relevance_summary(db_session, dataset.id)
    assert summary == {"metric": "answer_relevance", "count": 0, "average": None, "min": None, "max": None}
