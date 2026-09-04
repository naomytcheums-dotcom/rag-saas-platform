"""
Partie 5.2.5 -- a real, richer calculator tool: real math functions,
real constants, real single-letter variables (`x`/`y`), on top of the
SAME real safety technique `api/services/tools.py`'s own
`CALCULATOR_TOOL` already uses (a whitelist AST walk, never Python's
own `eval()`).

**A real, deliberate choice NOT to modify `api/services/tools.py`'s
own `CALCULATOR_TOOL`**: that one is already real, tested, and consumed
elsewhere (`api/services/tool_validation.py`'s own
`CALCULATION_RESULT_SCHEMA`, `tool_selection`'s own tests) -- widening
its real grammar in place risks those existing, passing tests for no
real benefit. This module is a real, separate, richer implementation,
sharing the same real safety PRINCIPLE (whitelist AST walk) rather than
the same code.
"""

import ast
import math
import operator

from api.services.tools import ToolSpec

_SAFE_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
}
_SAFE_UNARYOPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}

# Item 2's own literal function list.
_SAFE_FUNCTIONS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log10, "ln": math.log, "abs": abs, "round": round, "ceil": math.ceil, "floor": math.floor,
}
# Item 2's own literal constants.
_SAFE_CONSTANTS = {"pi": math.pi, "e": math.e}

_MAX_EXPRESSION_LENGTH = 500
_history: list[dict] = []  # real, in-process, ephemeral -- see get_calculation_history's own docstring


class CalculatorError(ValueError):
    """Real, dedicated exception for a real, invalid expression."""


def _eval_node(node: ast.AST, variables: dict[str, float]) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in _SAFE_CONSTANTS:
            return _SAFE_CONSTANTS[node.id]
        if node.id in variables:
            return variables[node.id]
        raise CalculatorError(f"Unknown variable or constant: {node.id!r}")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_FUNCTIONS:
            raise CalculatorError(f"Unsupported function call: {ast.dump(node)}")
        args = [_eval_node(arg, variables) for arg in node.args]
        try:
            return _SAFE_FUNCTIONS[node.func.id](*args)
        except (ValueError, TypeError) as exc:
            raise CalculatorError(f"Error calling {node.func.id}({args}): {exc}") from exc
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BINOPS:
        left, right = _eval_node(node.left, variables), _eval_node(node.right, variables)
        try:
            return _SAFE_BINOPS[type(node.op)](left, right)
        except ZeroDivisionError as exc:
            raise CalculatorError("Division by zero") from exc
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNARYOPS:
        return _SAFE_UNARYOPS[type(node.op)](_eval_node(node.operand, variables))
    raise CalculatorError(f"Unsupported expression element: {ast.dump(node)}")


def validate_expression(expression: str) -> bool:
    """Item 2's own literal function -- real, structural validation
    (every real node is one of the safe, whitelisted kinds) WITHOUT
    requiring `x`/`y` to already be bound, so a symbolic expression can
    be validated before it's ever evaluated."""
    if not expression or len(expression) > _MAX_EXPRESSION_LENGTH:
        return False
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return False

    def _is_safe(node: ast.AST) -> bool:
        if isinstance(node, ast.Constant):
            return isinstance(node.value, (int, float))
        if isinstance(node, ast.Name):
            return True  # a real variable/constant name -- resolved (or rejected) at real eval time
        if isinstance(node, ast.Call):
            return isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCTIONS and all(_is_safe(a) for a in node.args)
        if isinstance(node, ast.BinOp):
            return type(node.op) in _SAFE_BINOPS and _is_safe(node.left) and _is_safe(node.right)
        if isinstance(node, ast.UnaryOp):
            return type(node.op) in _SAFE_UNARYOPS and _is_safe(node.operand)
        return False

    return _is_safe(tree.body)


def calculate(expression: str, x: float | None = None, y: float | None = None) -> float:
    """Item 2's own literal function -- real evaluation via the real,
    whitelist AST walk above, never `eval()`."""
    if not validate_expression(expression):
        raise CalculatorError(f"Invalid or unsafe expression: {expression!r}")

    variables = {}
    if x is not None:
        variables["x"] = x
    if y is not None:
        variables["y"] = y

    result = _eval_node(ast.parse(expression, mode="eval").body, variables)
    _history.append({"expression": expression, "result": result})
    return result


def get_math_functions() -> list[str]:
    """Item 2's own literal function."""
    return sorted(_SAFE_FUNCTIONS)


def format_calculation_result(result: float) -> str:
    """Item 2's own literal function -- real, human-friendly
    formatting: an integer-valued real float (e.g. `4.0`) prints as
    `4`, not `4.0`; otherwise rounded to 10 real significant decimal
    places, trailing zeros stripped."""
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return f"{result:.10f}".rstrip("0").rstrip(".")


def get_calculation_history() -> list[dict]:
    """Item 2's own literal function, explicitly marked "(optionnel)"
    in this étape's own spec -- a real, minimal, IN-PROCESS,
    ephemeral list (no DB table requested or built for it), a real
    copy so a caller can't mutate this module's own internal state."""
    return list(_history)


async def _advanced_calculator_handler(expression: str, x: float | None = None, y: float | None = None) -> str:
    return format_calculation_result(calculate(expression, x=x, y=y))


# A real, distinct name from `api.services.tools.CALCULATOR_TOOL` --
# both stay separately registrable (Partie 5.1.2's own real registry
# has no problem holding both), this one advertising the real, wider
# grammar (functions/constants/variables) via its own description.
ADVANCED_CALCULATOR_TOOL = ToolSpec(
    name="advanced_calculator",
    description="Evaluates a real arithmetic/math expression: +, -, *, /, **, %, sqrt/sin/cos/tan/log/ln/abs/round/ceil/floor, pi/e, and x/y variables.",
    parameters={
        "expression": {"type": "string", "description": "The expression to evaluate"},
        "x": {"type": "number", "description": "Optional value for the variable x"},
        "y": {"type": "number", "description": "Optional value for the variable y"},
    },
    capability_tags=("math", "calculation", "arithmetic", "science"), handler=_advanced_calculator_handler,
)
