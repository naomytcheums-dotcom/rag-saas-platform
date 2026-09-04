"""Partie 3.3.4/3.3.5/3.3.6 -- tests for
api/services/retrieval_config.py's own real, standalone resolvers.

See that module's own top docstring for why these are honestly NOT
wired into a live retrieval call: no such call exists yet in api/."""

import pytest

from api.security.organization_settings import DEFAULT_SETTINGS
from api.services.retrieval_config import (
    RETRIEVAL_STRATEGIES,
    resolve_reranker_model,
    resolve_reranker_top_k,
    resolve_retrieval_strategy,
    resolve_score_threshold,
    resolve_top_k,
)

# ------------------------------- 3.3.4 retrieval strategy -------------------------------


def test_resolve_retrieval_strategy_falls_back_to_the_real_default():
    """Validation criterion: le fallback fonctionne."""
    assert resolve_retrieval_strategy() == DEFAULT_SETTINGS["retrieval_strategy"]


def test_resolve_retrieval_strategy_reads_from_real_organization_settings():
    """Validation criterion: la stratégie est lue depuis
    organization_settings."""
    assert resolve_retrieval_strategy({"retrieval_strategy": "vector_only"}) == "vector_only"


def test_resolve_retrieval_strategy_override_wins():
    assert resolve_retrieval_strategy({"retrieval_strategy": "vector_only"}, override="bm25_only") == "bm25_only"


def test_resolve_retrieval_strategy_accepts_every_real_literal_strategy():
    """Validation criterion: les différentes stratégies -- all 5 real,
    literal strategies from this étape's own spec are real, valid
    choices."""
    for strategy in RETRIEVAL_STRATEGIES:
        assert resolve_retrieval_strategy(override=strategy) == strategy
    assert len(RETRIEVAL_STRATEGIES) == 5


def test_resolve_retrieval_strategy_rejects_an_unsupported_value():
    """Validation criterion: robustesse -- stratégie non supportée."""
    with pytest.raises(ValueError):
        resolve_retrieval_strategy(override="magic")


# ---------------------------------- 3.3.5 reranker ---------------------------------------


def test_resolve_reranker_model_falls_back_to_the_real_default():
    assert resolve_reranker_model() == DEFAULT_SETTINGS["reranker_model"]


def test_resolve_reranker_model_reads_from_real_organization_settings():
    assert resolve_reranker_model({"reranker_model": "cross-encoder/ms-marco-MiniLM-L-12-v2"}) == "cross-encoder/ms-marco-MiniLM-L-12-v2"


def test_resolve_reranker_model_override_wins():
    assert resolve_reranker_model({"reranker_model": "x"}, override="cross-encoder/ms-marco-MiniLM-L-6-v2") == "cross-encoder/ms-marco-MiniLM-L-6-v2"


def test_resolve_reranker_model_allows_a_real_unlisted_model():
    assert resolve_reranker_model(override="cross-encoder/some-other-real-model") == "cross-encoder/some-other-real-model"


def test_resolve_reranker_model_rejects_the_malformed_literal_model_id():
    """Validation criterion: robustesse -- modèle non disponible. A
    real, documented flag: this literal model id from the étape's own
    spec mixes two different real HuggingFace namespaces."""
    with pytest.raises(ValueError, match="does not match real HuggingFace Hub naming"):
        resolve_reranker_model(override="cross-encoder/microsoft/deberta-v3-base")


def test_resolve_reranker_model_rejects_cohere_with_a_real_reason():
    with pytest.raises(ValueError, match="Cohere"):
        resolve_reranker_model(override="Cohere/rerank-english-v3.0")


# ----------------------------------- 3.3.6 top-k -----------------------------------------


def test_resolve_top_k_falls_back_to_the_real_default():
    """Validation criterion: le fallback fonctionne."""
    assert resolve_top_k() == DEFAULT_SETTINGS["top_k"]


def test_resolve_top_k_reads_from_real_organization_settings():
    assert resolve_top_k({"top_k": 20}) == 20


def test_resolve_top_k_override_wins():
    assert resolve_top_k({"top_k": 20}, override=3) == 3


def test_resolve_top_k_rejects_zero_and_negative():
    """Validation criterion: robustesse -- valeur invalide (0,
    négative)."""
    with pytest.raises(ValueError):
        resolve_top_k(override=0)
    with pytest.raises(ValueError):
        resolve_top_k(override=-5)


def test_resolve_top_k_rejects_a_real_too_large_value():
    """Validation criterion: robustesse -- valeur trop grande."""
    with pytest.raises(ValueError):
        resolve_top_k(override=1000)


def test_resolve_reranker_top_k_defaults_to_top_k_times_10():
    """Validation criterion: RERANKER_TOP_K = top_k * 10 par défaut."""
    assert resolve_reranker_top_k({"top_k": 5}) == 50
    assert resolve_reranker_top_k({"top_k": 20}) == 200


def test_resolve_reranker_top_k_override_wins():
    assert resolve_reranker_top_k({"top_k": 5}, override=999) == 999


# ------------------------------- 3.3.7 score threshold ------------------------------------


def test_resolve_score_threshold_falls_back_to_the_real_default():
    """Validation criterion: le fallback fonctionne."""
    assert resolve_score_threshold() == DEFAULT_SETTINGS["score_threshold"]


def test_resolve_score_threshold_reads_from_real_organization_settings():
    """Validation criterion: le seuil est lu depuis
    organization_settings."""
    assert resolve_score_threshold({"score_threshold": 0.8}) == 0.8


def test_resolve_score_threshold_override_wins():
    assert resolve_score_threshold({"score_threshold": 0.8}, override=0.2) == 0.2


def test_resolve_score_threshold_accepts_the_real_boundary_values():
    assert resolve_score_threshold(override=0.0) == 0.0
    assert resolve_score_threshold(override=1.0) == 1.0


def test_resolve_score_threshold_rejects_a_real_negative_value():
    """Validation criterion: robustesse -- seuil invalide (négatif)."""
    with pytest.raises(ValueError):
        resolve_score_threshold(override=-0.1)


def test_resolve_score_threshold_rejects_a_real_value_above_1():
    """Validation criterion: robustesse -- seuil invalide (> 1)."""
    with pytest.raises(ValueError):
        resolve_score_threshold(override=1.1)


def test_resolve_score_threshold_rejects_a_non_numeric_value():
    with pytest.raises(ValueError):
        resolve_score_threshold(override="high")  # type: ignore[arg-type]
