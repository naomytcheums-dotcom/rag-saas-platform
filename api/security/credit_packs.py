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
