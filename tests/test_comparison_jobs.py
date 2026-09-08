"""Partie 7.3.4/7.3.5/7.3.6/7.3.7 -- model/retriever/reranker/prompt
comparison jobs. Fast SQLite suite; litellm/search_with_context mocked
at the same boundary as tests/test_evaluation_results.py. The shared
engine (`run_comparison_job`) is exercised thoroughly via "model";
the other 3 types get lighter, type-specific coverage of their own
variant dispatch/validation."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.organization import Organization
from api.services.comparison_jobs import (
    create_model_comparison, create_prompt_comparison, create_reranker_comparison, create_retriever_comparison,
    get_comparison_results, list_model_comparisons, run_comparison_job,
)


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_dataset(db_session, org_id, question_count=2):
    dataset = EvaluationDataset(organization_id=org_id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    for i in range(question_count):
        db_session.add(EvaluationQuestion(dataset_id=dataset.id, question=f"Question {i}?"))
    await db_session.commit()
    return dataset


async def test_create_model_comparison_rejects_a_non_dict_variant(db_session):
    """Validation criterion: robustesse."""
    org = await _make_org(db_session, "Comparison Job Bad Variant Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id)

    with pytest.raises(ValueError):
        await create_model_comparison(db_session, dataset.id, "Bad", ["not-a-dict"])


async def test_run_model_comparison_ranks_real_configs(monkeypatch, db_session):
    """Validation criterion: la création/exécution de comparaison fonctionnent, les résultats sont corrects."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Comparison Job Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=2)

    job = await create_model_comparison(db_session, dataset.id, "GPT vs Claude", [{"temperature": 0.1}, {"temperature": 0.9}])
    await db_session.commit()
    assert job.results is None  # honestly not-yet-run

    updated = await run_comparison_job(db_session, job.id)

    assert updated.completed_at is not None
    assert updated.results["sample_size"] == 2
    assert len(updated.results["variants"]) == 2
    assert set(updated.results["ranking"]) == {0, 1}

    results = await get_comparison_results(db_session, job.id)
    assert results == updated.results


async def test_run_comparison_job_is_honestly_none_for_an_unknown_job(db_session):
    """Validation criterion: robustesse."""
    assert await run_comparison_job(db_session, uuid.uuid4()) is None


async def test_run_model_comparison_survives_one_real_variant_question_failing(monkeypatch, db_session):
    """Validation criterion: robustesse -- un modèle échoue."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    call_count = {"n": 0}

    async def _flaky_search(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated real failure")
        return []

    monkeypatch.setattr("api.services.evaluation_results.search_with_context", _flaky_search)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Comparison Job Flaky Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=2)
    job = await create_model_comparison(db_session, dataset.id, "Flaky", [{"temperature": 0.1}])
    await db_session.commit()

    updated = await run_comparison_job(db_session, job.id)

    assert updated.completed_at is not None
    assert len(updated.results["variants"][0]["result_ids"]) == 1  # one real question failed, one real succeeded


async def test_create_retriever_comparison_rejects_an_unknown_strategy(db_session):
    """Validation criterion (7.3.5): cohérence -- stratégies bien configurées."""
    org = await _make_org(db_session, "Retriever Comparison Bad Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id)

    with pytest.raises(ValueError):
        await create_retriever_comparison(db_session, dataset.id, "Bad", ["not-a-real-strategy"])


async def test_run_retriever_comparison_passes_the_real_strategy_override(monkeypatch, db_session):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    captured_kwargs = []

    async def _capture_search(*args, **kwargs):
        captured_kwargs.append(kwargs)
        return []

    monkeypatch.setattr("api.services.evaluation_results.search_with_context", _capture_search)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Retriever Comparison Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=1)
    job = await create_retriever_comparison(db_session, dataset.id, "Strategies", ["vector_only", "bm25_only"])
    await db_session.commit()

    await run_comparison_job(db_session, job.id)

    strategies_used = [kw.get("strategy") for kw in captured_kwargs]
    assert strategies_used == ["vector_only", "bm25_only"]


async def test_run_reranker_comparison_normalizes_to_hybrid_reranked(monkeypatch, db_session):
    """Validation criterion (7.3.6): un vrai override de reranker n'a
    d'effet réel que sous la stratégie hybrid_reranked -- normalisé
    automatiquement."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    captured_kwargs = []

    async def _capture_search(*args, **kwargs):
        captured_kwargs.append(kwargs)
        return []

    monkeypatch.setattr("api.services.evaluation_results.search_with_context", _capture_search)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Reranker Comparison Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=1)
    job = await create_reranker_comparison(db_session, dataset.id, "Rerankers", ["cross-encoder/ms-marco-MiniLM-L-6-v2"])
    await db_session.commit()

    await run_comparison_job(db_session, job.id)

    assert captured_kwargs[0]["strategy"] == "hybrid_reranked"
    assert captured_kwargs[0]["reranker"] == "cross-encoder/ms-marco-MiniLM-L-6-v2"


async def test_run_prompt_comparison_overrides_the_real_system_prompt(monkeypatch, db_session):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    mock_acompletion = AsyncMock(return_value=_real_response("An answer."))
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Prompt Comparison Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=1)
    job = await create_prompt_comparison(db_session, dataset.id, "Prompts", ["Be extremely terse."])
    await db_session.commit()

    await run_comparison_job(db_session, job.id)

    system_message = mock_acompletion.call_args.kwargs["messages"][0]["content"]
    assert "Be extremely terse." in system_message


async def test_list_model_comparisons_paginates(db_session):
    org = await _make_org(db_session, "Comparison List Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=0)
    for i in range(3):
        await create_model_comparison(db_session, dataset.id, f"C{i}", [{}])
    await db_session.commit()

    page = await list_model_comparisons(db_session, dataset.id, limit=2, offset=0)
    assert page["total"] == 3
    assert len(page["items"]) == 2
