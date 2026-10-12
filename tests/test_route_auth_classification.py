"""Specs 1.2.7, 10.1.4 - every operation without a declared security scheme is on a reviewed list, with the reason it is open.

`tests/data/public_operations.json` maps "METHOD /path" to why that operation can be called without a bearer token (API key, provider signature,
one-time token, public catalog...). A NEW unauthenticated route fails this test until its author either protects it or adds it to the list with a
reason that a reviewer can check. A route that disappears also fails, so the list cannot go stale.
"""

import json
from pathlib import Path

from api.main import app

LISTED = json.loads((Path(__file__).parent / "data" / "public_operations.json").read_text(encoding="utf-8"))
METHODS = ("get", "post", "put", "patch", "delete")


def _operations_without_security() -> set[str]:
    schema = app.openapi()
    return {
        f"{method.upper()} {path}"
        for path, item in schema["paths"].items()
        for method, operation in item.items()
        if method in METHODS and not operation.get("security") and not schema.get("security")
    }


def test_no_operation_is_open_without_being_reviewed():
    open_now = _operations_without_security()
    unreviewed = sorted(open_now - set(LISTED))
    assert not unreviewed, f"unauthenticated operations missing from tests/data/public_operations.json (protect them or document why they are open): {unreviewed}"


def test_the_reviewed_list_contains_no_removed_operation():
    stale = sorted(set(LISTED) - _operations_without_security())
    assert not stale, f"listed as open but no longer open or no longer existing: {stale}"


def test_every_listed_operation_has_a_real_reason():
    assert all(reason and reason != "TO CLASSIFY" for reason in LISTED.values())
