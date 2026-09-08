"""Partie 7.2.11 -- citation correctness. Fast, pure-Python suite."""

import uuid

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion, EvaluationResult
from api.models.organization import Organization
from api.services.citation_correctness import calculate_citation_correctness, get_citation_correctness_summary


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


_CONTEXT = "[1] The clinical study included 500 participants in 2020.\n\n[2] Bananas are a good source of potassium."


def test_calculate_citation_correctness_is_high_for_a_real_correct_citation():
    """Validation criterion: citation correcte."""
    answer = "The clinical study included 500 participants in 2020 [1]."
    citations = [{"text": "The clinical study included 500 participants in 2020."}, {"text": "Bananas are a good source of potassium."}]
    result = calculate_citation_correctness(answer, citations, _CONTEXT)
    assert result["score"] > 0.6
    assert set(result["factors"]) == {"citation_presence", "citation_accuracy", "citation_format", "citation_completeness"}


def test_calculate_citation_correctness_is_low_for_a_real_incorrect_citation():
    """Validation criterion: citation incorrecte -- marker points to an
    unrelated real source."""
    answer = "The clinical study included 500 participants in 2020 [2]."
    citations = [{"text": "The clinical study included 500 participants in 2020."}, {"text": "Bananas are a good source of potassium."}]
    correct = calculate_citation_correctness("The clinical study included 500 participants in 2020 [1].", citations, _CONTEXT)
    incorrect = calculate_citation_correctness(answer, citations, _CONTEXT)
    assert incorrect["factors"]["citation_accuracy"] < correct["factors"]["citation_accuracy"]


def test_calculate_citation_correctness_is_honestly_low_for_a_real_missing_citation():
    """Validation criterion: citation manquante."""
    answer = "The clinical study included 500 participants in 2020."
    result = calculate_citation_correctness(answer, [{"text": "The clinical study included 500 participants in 2020."}], _CONTEXT)
    assert result["factors"]["citation_presence"] == 0.0
    assert result["factors"]["citation_completeness"] == 0.0


def test_calculate_citation_correctness_presence_flags_a_real_out_of_range_marker():
    answer = "This claims something [99]."
    result = calculate_citation_correctness(answer, [{"text": "x"}], _CONTEXT)
    assert result["factors"]["citation_presence"] == 0.0


def test_calculate_citation_correctness_format_flags_a_real_malformed_marker():
    well_formed = calculate_citation_correctness("A claim [1].", [{"text": "A claim."}], _CONTEXT)
    malformed = calculate_citation_correctness("A claim [see 1, page 3].", [{"text": "A claim."}], _CONTEXT)
    assert malformed["factors"]["citation_format"] < well_formed["factors"]["citation_format"]


def test_calculate_citation_correctness_is_honestly_zero_for_an_empty_answer():
    """Validation criterion: robustesse -- pas de citations."""
    result = calculate_citation_correctness("", [], None)
    assert result["score"] == 0.0
    assert all(v == 0.0 for v in result["factors"].values())


def test_calculate_citation_correctness_honors_the_real_check_toggles(monkeypatch):
    """Validation criterion: robustesse -- un facteur désactivé n'entraîne
    jamais artificiellement le score vers 0."""
    monkeypatch.setattr(settings, "CITATION_CORRECTNESS_CHECK_ACCURACY", False)
    answer = "The clinical study included 500 participants in 2020 [1]."
    result = calculate_citation_correctness(answer, [{"text": "unrelated"}], _CONTEXT)
    assert result["factors"]["citation_accuracy"] is None


async def test_get_citation_correctness_summary_averages_the_real_stored_metric(db_session):
    org = await _make_org(db_session, "Citation Correctness Summary Org")
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?")
    db_session.add(question)
    await db_session.flush()
    result = EvaluationResult(
        question_id=question.id, model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
        actual_answer="a", metrics={"citation_correctness": 0.9}, latency_ms=10,
    )
    db_session.add(result)
    await db_session.commit()

    summary = await get_citation_correctness_summary(db_session, dataset.id)
    assert summary["average"] == 0.9
