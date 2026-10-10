"""Spec 13.1.1 - type annotations are measured and can only go up (a ratchet, not a claim that they are everywhere)."""

import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("type_hint_coverage", Path(__file__).resolve().parents[1] / "scripts" / "type_hint_coverage.py")
module = importlib.util.module_from_spec(spec)
sys.modules["type_hint_coverage"] = module
spec.loader.exec_module(module)

# Measured on 2026-10-10: 69.1 %. Raise this number when you annotate more; never lower it.
FLOOR_PERCENT = 69.0


def test_annotation_coverage_does_not_fall():
    annotated, total, _missing = module.measure()
    assert 100 * annotated / total >= FLOOR_PERCENT, f"{annotated}/{total} functions annotated"


def test_a_function_is_annotated_only_when_every_part_is():
    import ast

    def parse(source):
        return ast.parse(source).body[0]

    assert module.function_is_annotated(parse("def f(a: int, *args: str, **kw: str) -> None: ..."))
    assert not module.function_is_annotated(parse("def f(a: int): ..."))
    assert not module.function_is_annotated(parse("def f(a) -> None: ..."))
    assert module.function_is_annotated(parse("class C:\n  def m(self, a: int) -> int: ...").body[0])
