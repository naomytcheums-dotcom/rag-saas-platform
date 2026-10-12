"""Measure how many functions in api/ carry type annotations (spec 13.1.1).

    python scripts/type_hint_coverage.py            # prints the figures
    python scripts/type_hint_coverage.py --worst 15 # also lists the files with the most unannotated functions

A function counts as annotated when it has a return annotation AND every parameter (except self / cls) is annotated. Standard library only.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def function_is_annotated(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if node.returns is None:
        return False
    args = node.args
    params = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if args.vararg:
        params.append(args.vararg)
    if args.kwarg:
        params.append(args.kwarg)
    return all(p.annotation is not None for p in params if p.arg not in ("self", "cls"))


def measure(directory: Path = ROOT / "api") -> tuple[int, int, dict[str, int]]:
    total = annotated = 0
    missing_by_file: dict[str, int] = {}
    for path in sorted(directory.rglob("*.py")):
        if "alembic" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total += 1
                if function_is_annotated(node):
                    annotated += 1
                else:
                    key = str(path.relative_to(ROOT)).replace("\\", "/")
                    missing_by_file[key] = missing_by_file.get(key, 0) + 1
    return annotated, total, missing_by_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worst", type=int, default=0)
    args = parser.parse_args()
    annotated, total, missing = measure()
    print(f"{annotated}/{total} functions fully annotated ({100 * annotated / total:.1f} %)")
    for name, count in sorted(missing.items(), key=lambda kv: -kv[1])[: args.worst]:
        print(f"  {count:4d}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
