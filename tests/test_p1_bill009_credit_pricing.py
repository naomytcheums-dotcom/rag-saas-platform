"""BILL-009: credit pricing must follow what the model costs the platform (a dearer model is charged proportionally more credits;
the default model keeps the flat rate; models missing from the platform table are priced from the LiteLLM price map)."""

from api.config import settings


def test_the_default_model_keeps_the_flat_credit_rate():
    from api.security.credit_packs import credits_for_llm_usage

    assert credits_for_llm_usage(1000, 500, "claude-sonnet-5-5") == 10 + 10
    assert credits_for_llm_usage(150, 70, "anthropic/claude-sonnet-5-5") == 2 + 2


def test_a_dearer_model_costs_proportionally_more_credits_and_a_cheaper_one_never_less():
    from api.security.credit_packs import credits_for_llm_usage

    default = credits_for_llm_usage(1_000_000, 1_000_000, "claude-sonnet-5-5")
    assert credits_for_llm_usage(1_000_000, 1_000_000, "claude-3-5-sonnet") > default  # 3/15 vs 2/10
    assert credits_for_llm_usage(1_000_000, 1_000_000, "gpt-4o-mini") == default  # cheaper: never discounted below the flat rate


def test_models_missing_from_the_platform_table_are_priced_from_the_litellm_map():
    import litellm

    from api.security.credit_packs import credits_for_llm_usage

    expensive = [name for name, entry in litellm.model_cost.items() if (entry.get("output_cost_per_token") or 0) * 1e6 >= 50 and "/" not in name]
    assert expensive, "the installed price map lists no expensive model to compare with"
    assert credits_for_llm_usage(0, 1_000_000, expensive[0]) > credits_for_llm_usage(0, 1_000_000, "claude-sonnet-5-5") * 4


def test_an_unknown_model_uses_the_configured_multiplier(monkeypatch):
    from api.security.credit_packs import credits_for_llm_usage

    assert credits_for_llm_usage(1000, 500, "totally-unknown-model") == 20
    monkeypatch.setattr(settings, "CREDITS_UNKNOWN_MODEL_MULTIPLIER", 3.0)
    assert credits_for_llm_usage(1000, 500, "totally-unknown-model") == 60
    assert credits_for_llm_usage(1000, 500, None) == 60
