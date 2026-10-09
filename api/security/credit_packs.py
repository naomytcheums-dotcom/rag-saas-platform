"""
Partie 12.3 -- fixed credit packs. A static Python catalog, same
"fixed constants, not a DB table nobody edits" pattern as
api/security/permission_catalog.py's 52 permissions: nothing in this
codebase's real spec ever asks an admin to invent a 5th pack at
runtime, so a table (and its CRUD, and its migration) would be pure
overhead for data that's really a deploy-time constant.

Conversion rates match the literal spec exactly (1 credit = 1 API
request, 100 input tokens, 50 output tokens, or 1 processed document;
10 credits = 1 MB storage).
"""

CREDIT_PACKS: list[dict] = [
    {"id": "starter", "name": "Starter", "credits": 10_000, "price_cents": 999},
    {"id": "pro", "name": "Pro", "credits": 100_000, "price_cents": 7999},
    {"id": "business", "name": "Business", "credits": 500_000, "price_cents": 34999},
    {"id": "enterprise", "name": "Enterprise", "credits": 1_000_000, "price_cents": 59999},
]

CREDIT_CONVERSION = {
    "api_request": 1,       # 1 credit = 1 API request
    "tokens_input": 100,    # 1 credit = 100 input tokens
    "tokens_output": 50,    # 1 credit = 50 output tokens
    "document": 1,          # 1 credit = 1 document processed
    "storage_mb": 0.1,      # 10 credits = 1 MB of storage
}


def get_credit_pack(pack_id: str) -> dict | None:
    return next((p for p in CREDIT_PACKS if p["id"] == pack_id), None)


def credits_for_usage(metric: str, amount: int) -> int:
    """How many credits `amount` units of `metric` are worth, rounded up
    so a partial unit never under-charges.

    Real bug fixed here (2026-09-17, found via the first live caller
    this function ever had -- api/services/agent_orchestrator.py's real
    per-LLM-call credit debit): `CREDIT_CONVERSION`'s rates are units-
    PER-credit (its own docstring: "1 credit = 100 input tokens" means
    100 tokens per credit), so converting a real usage amount into
    credits is `amount / rate`, not `amount * rate` -- the previous
    formula charged 500 input tokens as 50,000 credits instead of 5,
    a 10,000x overcharge that nothing had caught yet because nothing
    had ever called this function until now."""
    rate = CREDIT_CONVERSION.get(metric)
    if not rate:
        return 0
    import math

    return math.ceil(amount / rate)


def _price_per_million(model: str | None) -> dict | None:
    """$/M-token price of `model`: the platform's own table first, then the installed LiteLLM price map."""
    from api.services.cost_tracking import find_pricing

    pricing = find_pricing(model)
    if pricing is not None:
        return pricing
    if not model:
        return None
    try:
        import litellm

        for key in (model, model.split("/", 1)[-1]):
            entry = litellm.model_cost.get(key)
            if entry and entry.get("input_cost_per_token") is not None and entry.get("output_cost_per_token") is not None:
                return {"input": entry["input_cost_per_token"] * 1_000_000, "output": entry["output_cost_per_token"] * 1_000_000}
    except Exception:  # noqa: BLE001 -- a missing price map must never break billing
        return None
    return None


def credits_for_llm_usage(prompt_tokens: int, completion_tokens: int, model: str | None) -> int:
    """BILL-009 -- credits for one LLM call, scaled by what the model really costs the platform.

    The flat conversion (1 credit = 100 input / 50 output tokens) is calibrated on the default model. A dearer model costs more per
    token, so each direction is multiplied by (model price / baseline price) when the model is dearer than the baseline; a cheaper
    one is never discounted. A model with no known price is charged `CREDITS_UNKNOWN_MODEL_MULTIPLIER` (1.0 by default)."""
    import math

    from api.config import settings

    pricing = _price_per_million(model)
    if pricing is None:
        input_factor = output_factor = max(settings.CREDITS_UNKNOWN_MODEL_MULTIPLIER, 1.0)
    else:
        input_factor = max(pricing["input"] / settings.CREDITS_BASELINE_INPUT_USD_PER_M, 1.0)
        output_factor = max(pricing["output"] / settings.CREDITS_BASELINE_OUTPUT_USD_PER_M, 1.0)
    return math.ceil((prompt_tokens / CREDIT_CONVERSION["tokens_input"]) * input_factor) + math.ceil(
        (completion_tokens / CREDIT_CONVERSION["tokens_output"]) * output_factor
    )
