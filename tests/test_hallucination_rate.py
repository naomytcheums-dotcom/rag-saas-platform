"""Partie 7.2.12 -- hallucination rate. Fast, pure-Python suite."""

import uuid

from api.models.evaluation import EvaluationDataset, EvaluationQuestion, EvaluationResult
from api.models.organization import Organization
from api.services.hallucination_rate import calculate_hallucination_rate, get_hallucination_rate_summary


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


def test_calculate_hallucination_rate_is_low_for_a_real_well_supported_answer():
    """Validation criterion: hallucination faible."""
    answer = "The clinical study included exactly 500 participants total in 2020 and was published in a peer reviewed journal."
    citations = [{"text": answer}]
    result = calculate_hallucination_rate(answer, citations, context=answer)
    assert result["score"] < 0.5
    assert set(result["factors"]) == {"unsupported_claims_ratio", "contradiction_rate", "source_coverage", "confidence_estimation"}


def test_calculate_hallucination_rate_is_high_for_a_real_contradicting_citation():
    """Validation criterion: hallucination élevée."""
    answer = "The clinical study included exactly 500 participants total in 2020 and was published in a peer reviewed journal."
    contradicting = [{"text": "The clinical study included exactly 800 participants total in 2020 and was published in a peer reviewed journal."}]
    result = calculate_hallucination_rate(answer, contradicting)
    assert result["factors"]["contradiction_rate"] == 1.0


def test_calculate_hallucination_rate_is_honestly_zero_for_an_empty_response():
    """Validation criterion: robustesse -- réponse courte/vide."""
    result = calculate_hallucination_rate("", [])
    assert result["score"] == 0.0
    assert result["reliable"] is False


def test_calculate_hallucination_rate_is_null_for_no_real_hallucination_at_all():
    """Validation criterion: hallucination nulle."""
    answer = "The clinical study included exactly 500 participants total in 2020."
    citations = [{"text": answer}]
    result = calculate_hallucination_rate(answer, citations, context=answer)
    assert result["factors"]["unsupported_claims_ratio"] == 0.0
    assert result["factors"]["contradiction_rate"] == 0.0


def test_calculate_hallucination_rate_flags_reliability_below_min_claims():
    """Validation criterion: robustesse -- réponse courte -- peu de
    real claims marks the real result as unreliable, never a crash."""
    result = calculate_hallucination_rate("It works.", [{"text": "It works."}])
    assert result["reliable"] is False


def test_calculate_hallucination_rate_source_coverage_reflects_real_unused_sources():
    answer = "The clinical study included exactly 500 participants total in 2020."
    used = calculate_hallucination_rate(answer, [{"text": answer}])
    unused = calculate_hallucination_rate(answer, [{"text": "Completely unrelated real content about gardening."}])
    assert unused["factors"]["source_coverage"] < used["factors"]["source_coverage"]


async def test_get_hallucination_rate_summary_averages_the_real_stored_metric(db_session):
    org = await _make_org(db_session, "Hallucination Rate Summary Org")
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?")
    db_session.add(question)
    await db_session.flush()
    result = EvaluationResult(
        question_id=question.id, model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
        actual_answer="a", metrics={"hallucination_rate": 0.1}, latency_ms=10,
    )
    db_session.add(result)
    await db_session.commit()

    summary = await get_hallucination_rate_summary(db_session, dataset.id)
    assert summary["average"] == 0.1
