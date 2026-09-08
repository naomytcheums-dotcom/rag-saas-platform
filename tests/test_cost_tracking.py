"""Partie 7.2.15 -- cost/request. Fast, pure-Python suite."""

import uuid

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion, EvaluationResult
from api.models.organization import Organization
from api.services.cost_tracking import calculate_cost_per_request, get_cost_summary


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


def test_calculate_cost_per_request_matches_a_real_default_resolved_model_name():
    """Validation criterion: le calcul de Cost/request fonctionne --
    matches this codebase's own real, versioned resolved model string,
    not just a bare literal pricing-table key."""
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000, "total_tokens": 2_000_000, "model": "claude-3-5-sonnet-20241022"}
    result = calculate_cost_per_request(usage, {})
    assert result["pricing_available"] is True
    assert result["cost_per_request"] == 3.0 + 15.0


def test_calculate_cost_per_request_prefers_the_longest_real_matching_key():
    """Validation criterion: tarifs différents -- gpt-4o-mini doit
    utiliser son propre tarif, pas celui de gpt-4o (dont il contient
    le nom en tant que sous-chaîne réelle)."""
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 0, "total_tokens": 1_000_000, "model": "gpt-4o-mini"}
    result = calculate_cost_per_request(usage, {})
    assert result["cost_per_request"] == settings.COST_MODEL_PRICING["gpt-4o-mini"]["input"]


def test_calculate_cost_per_request_is_honest_with_an_unknown_real_model():
    """Validation criterion: robustesse -- modèle absent de la liste."""
    usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "model": "some-unpriced-model-v9"}
    result = calculate_cost_per_request(usage, {})
    assert result["pricing_available"] is False
    assert result["cost_per_request"] is None


def test_calculate_cost_per_request_is_honest_with_no_real_token_usage_at_all():
    """Validation criterion: robustesse."""
    result = calculate_cost_per_request(None, {})
    assert result["pricing_available"] is False


def test_calculate_cost_per_request_uses_model_config_over_token_usage_model(monkeypatch):
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 0, "total_tokens": 1_000_000, "model": "gpt-4o-mini"}
    result = calculate_cost_per_request(usage, {"model": "mistral-small-latest"})
    assert result["cost_per_request"] == settings.COST_MODEL_PRICING["mistral-small"]["input"]


def test_calculate_cost_per_request_is_honest_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "COST_TRACKING_ENABLED", False)
    usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "model": "claude-3-5-sonnet-20241022"}
    result = calculate_cost_per_request(usage, {})
    assert result["pricing_available"] is False


async def test_get_cost_summary_averages_the_real_stored_metric(db_session):
    org = await _make_org(db_session, "Cost Summary Org")
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?")
    db_session.add(question)
    await db_session.flush()
    result = EvaluationResult(
        question_id=question.id, model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
        actual_answer="a", metrics={"cost_per_request": 0.05}, latency_ms=10,
    )
    db_session.add(result)
    await db_session.commit()

    summary = await get_cost_summary(db_session, dataset.id)
    assert summary["average"] == 0.05
