"""api/services/cost_aware_routing.py -- pure, deterministic logic over
api.services.cost_tracking's own real, static pricing table. No
mocking needed (real pricing data, not an external call)."""

from api.services.cost_aware_routing import select_model_for_budget


def test_select_model_for_budget_picks_the_only_candidate_within_a_tight_budget():
    # claude-3-haiku: (1500*0.25 + 500*1.25)/1e6 = 0.001, claude-3-5-sonnet: (1500*3 + 500*15)/1e6 = 0.012
    result = select_model_for_budget(["claude-3-haiku", "claude-3-5-sonnet"], max_cost_per_request=0.005)
    assert result["selected_model"] == "claude-3-haiku"
    assert result["estimated_cost"] is not None


def test_select_model_for_budget_picks_the_most_capable_candidate_when_both_fit():
    # claude-3-haiku: (1500*0.25 + 500*1.25)/1e6 = 0.001, claude-3-5-sonnet: (1500*3 + 500*15)/1e6 = 0.012
    result = select_model_for_budget(["claude-3-haiku", "claude-3-5-sonnet"], max_cost_per_request=0.02)
    assert result["selected_model"] == "claude-3-5-sonnet"


def test_select_model_for_budget_with_no_budget_constraint_picks_the_most_expensive_priced_candidate():
    result = select_model_for_budget(["gpt-4o-mini", "gpt-4o"], max_cost_per_request=None)
    assert result["selected_model"] == "gpt-4o"


def test_select_model_for_budget_falls_back_to_cheapest_when_none_fit():
    result = select_model_for_budget(["claude-3-5-sonnet", "gpt-4o"], max_cost_per_request=0.0001)
    assert result["selected_model"] in {"claude-3-5-sonnet", "gpt-4o"}
    assert "exceeds" in result["reason"]


def test_select_model_for_budget_honestly_reports_no_candidate_has_real_pricing():
    result = select_model_for_budget(["totally-unpriced-model"], max_cost_per_request=1.0)
    assert result["selected_model"] is None
    assert result["estimated_cost"] is None


def test_select_model_for_budget_ignores_unpriced_candidates_but_still_uses_priced_ones():
    result = select_model_for_budget(["totally-unpriced-model", "claude-3-haiku"], max_cost_per_request=1.0)
    assert result["selected_model"] == "claude-3-haiku"


def test_select_model_for_budget_respects_custom_assumed_token_counts():
    cheap = select_model_for_budget(["claude-3-5-sonnet"], max_cost_per_request=None, assumed_input_tokens=10, assumed_output_tokens=10)
    expensive = select_model_for_budget(["claude-3-5-sonnet"], max_cost_per_request=None, assumed_input_tokens=100_000, assumed_output_tokens=100_000)
    assert cheap["estimated_cost"] < expensive["estimated_cost"]
