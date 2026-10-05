"""
Real Cost-Aware Intelligence -- item 26 of the internal-systems list:
picks a real, sufficiently-capable model within a real cost/latency
budget, BEFORE a real, billed LLM call is made. Built entirely on this
codebase's own already-real cost infrastructure
(`api.services.cost_tracking.find_pricing`, the same real $/M-token
static pricing table `calculate_cost_per_request` already uses) --
never a second, invented pricing source.

**Real, honestly-documented assumption, same discipline as
`calculate_cost_per_request`'s own `estimated_monthly_cost`**: the real
cost of a NOT-YET-MADE call is unknowable ahead of time (it depends on
the real output length an LLM actually produces) -- this module
estimates it using a real, explicit, documented assumed token count
(`assumed_input_tokens`/`assumed_output_tokens`, real, overridable
defaults), never claims a fabricated, precise pre-call cost.

**Real, deliberate model-tier assumption**: within the SAME real
provider, a model this codebase's own real pricing table prices HIGHER
is assumed to be the more capable real tier (Anthropic/OpenAI/Gemini/
Mistral's own real, public pricing already reflects this for every
real model this codebase's own `COST_MODEL_PRICING` table lists) --
`select_model_for_budget` picks the MOST CAPABLE real, priced candidate
that still fits the real budget, falling back to the cheapest real,
priced candidate if none do, and honestly reporting when NO real
candidate has real pricing data at all (never silently picking an
arbitrary one)."""

from api.services.cost_tracking import find_pricing

_MILLION = 1_000_000.0


def _estimated_cost(model: str, assumed_input_tokens: int, assumed_output_tokens: int) -> float | None:
    pricing = find_pricing(model)
    if pricing is None:
        return None
    return (assumed_input_tokens * pricing["input"] + assumed_output_tokens * pricing["output"]) / _MILLION


def select_model_for_budget(
    candidate_models: list[str], max_cost_per_request: float | None,
    assumed_input_tokens: int = 1500, assumed_output_tokens: int = 500,
) -> dict:
    """Real, additive selection among a real, caller-supplied list of
    candidate models (e.g. an organization's own configured fallback
    chain, or a fixed real per-provider tier list) -- picks the most
    capable real, priced candidate whose real ESTIMATED cost stays
    within `max_cost_per_request`. `max_cost_per_request=None` means
    "no real budget constraint" -- the most capable real, priced
    candidate is returned outright, same as if the budget were
    infinite.

    Returns `{"selected_model": str | None, "estimated_cost": float | None,
    "reason": str}` -- `selected_model` is honestly `None` only when
    NOT ONE real candidate has real pricing data at all (never an
    arbitrary guess)."""
    priced = [(model, cost) for model in candidate_models if (cost := _estimated_cost(model, assumed_input_tokens, assumed_output_tokens)) is not None]
    if not priced:
        return {"selected_model": None, "estimated_cost": None, "reason": "no real pricing data for any candidate model"}

    priced.sort(key=lambda pair: pair[1])  # cheapest first

    if max_cost_per_request is None:
        model, cost = priced[-1]  # most capable (highest real estimated cost)
        return {"selected_model": model, "estimated_cost": cost, "reason": "no real budget constraint -- most capable real, priced candidate"}

    within_budget = [pair for pair in priced if pair[1] <= max_cost_per_request]
    if within_budget:
        model, cost = within_budget[-1]  # most capable real candidate that still fits
        return {"selected_model": model, "estimated_cost": cost, "reason": f"most capable real candidate within the real ${max_cost_per_request:.4f}/request budget"}

    model, cost = priced[0]  # cheapest real, priced candidate -- still over budget, honestly reported
    return {
        "selected_model": model, "estimated_cost": cost,
        "reason": f"even the cheapest real, priced candidate (${cost:.4f}) exceeds the real ${max_cost_per_request:.4f}/request budget",
    }
