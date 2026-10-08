"""api/services/query_router.py -- pure, deterministic heuristic logic,
no mocking needed. Every real suggestion is checked against
api.services.retrieval_config.RETRIEVAL_STRATEGIES -- never a
fabricated strategy value search() wouldn't actually accept."""

from api.services.retrieval_config import RETRIEVAL_STRATEGIES
from api.services.query_router import suggest_retrieval_strategy


def test_suggest_retrieval_strategy_always_returns_a_real_valid_strategy():
    for query in ["What is the refund policy?", "compare X and Y", "refund", "", "   "]:
        result = suggest_retrieval_strategy(query)
        assert result["strategy"] in RETRIEVAL_STRATEGIES


def test_suggest_retrieval_strategy_detects_real_multi_hop_language():
    for query in [
        "Compare the refund policy of plan A and plan B",
        "What is the difference between the free tier and the pro tier?",
        "What is the relationship between latency and cost?",
        "revenue across all regions",
    ]:
        result = suggest_retrieval_strategy(query)
        assert result["strategy"] == "hybrid_reranked", query
        assert result["graphrag_recommended"] is True


def test_suggest_retrieval_strategy_detects_a_real_short_keyword_query():
    result = suggest_retrieval_strategy("refund policy")
    assert result["strategy"] == "bm25_only"
    assert result["graphrag_recommended"] is False


def test_suggest_retrieval_strategy_defaults_to_hybrid_for_an_ordinary_question():
    result = suggest_retrieval_strategy("What is the process for requesting a refund on a digital purchase?")
    assert result["strategy"] == "hybrid"


def test_suggest_retrieval_strategy_handles_an_empty_query_safely():
    result = suggest_retrieval_strategy("")
    assert result["strategy"] == "hybrid"
    assert result["graphrag_recommended"] is False


def test_suggest_retrieval_strategy_a_short_query_with_a_question_word_is_not_bm25_only():
    """Validation criterion: 'how' is a real question word -- a short
    query containing one should NOT be treated as a bare keyword
    lookup."""
    result = suggest_retrieval_strategy("how refunds work")
    assert result["strategy"] != "bm25_only"
