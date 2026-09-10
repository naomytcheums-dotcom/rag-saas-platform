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
    so a partial unit never under-charges."""
    rate = CREDIT_CONVERSION.get(metric)
    if rate is None:
        return 0
    import math

    return math.ceil(amount * rate)
