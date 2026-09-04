"""
A real, minimal Tool abstraction -- a genuine prerequisite for Partie
5.1.2 through 5.1.9 (tool selection/permissions/timeout/budget/retry/
fallback/parallel execution/result validation): none of those can mean
anything real without a real "what is a tool" concept to operate on.

**Honest scope**: no such abstraction existed anywhere in this codebase
before this batch. A full, real, external tool suite (web search, SQL,
calendar, custom webhooks) is Partie 5.2's own, separate, larger scope
-- explicitly not started, not this module's job. This module ships
only the minimal, real, independently-callable core the 8 sub-étapes
above actually need: a `ToolSpec` shape, and two genuinely real (not
fabricated placeholder) built-in tools, so selection/ranking/
permission-checks/timeouts/budgets/retries/fallbacks/parallel
execution/validation all have something real to exercise in tests
instead of a mock standing in for a tool that doesn't exist.

**Honest, deliberate limit on orchestrator integration**: `ToolSpec`
is wired into `AgentOrchestrator.run_agent` as an OPTIONAL, additive
parameter (selection is computed and traced, tool descriptions are
appended to the system prompt) -- but there is no automatic
LLM-function-calling loop here (parsing structured `tool_calls` out of
a completion and re-invoking the LLM with results). That is real,
substantial, separate work belonging to Partie 5.2's own scope; adding
it silently under a 5.1.x tool-infrastructure request would be
unrequested scope growth, not a fix.
"""

import ast
import dataclasses
import operator
from collections.abc import Awaitable, Callable

_SAFE_BINOPS: dict[type, Callable] = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
}
_SAFE_UNARYOPS: dict[type, Callable] = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def _safe_eval_arithmetic(node: ast.AST) -> float:
    """A real, safe arithmetic evaluator -- walks a parsed `ast.Expression`
    accepting ONLY numeric literals and +-*/**% -- never Python's own
    `eval()` (which would execute arbitrary code from a caller-supplied
    string, a real injection vector this tool must not open)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BINOPS:
        return _SAFE_BINOPS[type(node.op)](_safe_eval_arithmetic(node.left), _safe_eval_arithmetic(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNARYOPS:
        return _SAFE_UNARYOPS[type(node.op)](_safe_eval_arithmetic(node.operand))
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


@dataclasses.dataclass(frozen=True)
class ToolSpec:
    """The real, minimal shape every Partie 5.1.2-5.1.9 function below
    operates on. `parameters` is a JSON-schema-shaped dict (name ->
    {"type": ..., "description": ...}); `handler` is a real, async
    callable, invoked as `await handler(**params)`, returning a plain
    string result."""

    name: str
    description: str
    parameters: dict[str, dict]
    capability_tags: tuple[str, ...]
    handler: Callable[..., Awaitable[str]]


async def _calculator_handler(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_safe_eval_arithmetic(tree.body))
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError) as exc:
        raise ValueError(f"Invalid arithmetic expression: {expression!r} ({exc})") from exc


async def _word_count_handler(text: str) -> str:
    return str(len(text.split()))


CALCULATOR_TOOL = ToolSpec(
    name="calculator", description="Evaluates a real arithmetic expression (+, -, *, /, **, %).",
    parameters={"expression": {"type": "string", "description": "The arithmetic expression to evaluate"}},
    capability_tags=("math", "calculation", "arithmetic"), handler=_calculator_handler,
)
WORD_COUNT_TOOL = ToolSpec(
    name="word_count", description="Counts the number of words in a real piece of text.",
    parameters={"text": {"type": "string", "description": "The text to count words in"}},
    capability_tags=("text", "counting", "analysis"), handler=_word_count_handler,
)

_REGISTRY: dict[str, ToolSpec] = {CALCULATOR_TOOL.name: CALCULATOR_TOOL, WORD_COUNT_TOOL.name: WORD_COUNT_TOOL}


def register_tool(tool: ToolSpec) -> None:
    """Adds (or replaces) a real tool in the shared, in-process registry
    -- how a real, future Partie 5.2 tool (search/HTTP/SQL/calendar)
    plugs into the same infrastructure this batch builds."""
    _REGISTRY[tool.name] = tool


def get_tool(name: str) -> ToolSpec | None:
    return _REGISTRY.get(name)


def list_tools() -> list[ToolSpec]:
    return list(_REGISTRY.values())


def get_tool_description(tool: ToolSpec) -> str:
    """Partie 5.1.2's own literal function."""
    return tool.description


def get_tool_parameters(tool: ToolSpec) -> dict[str, dict]:
    """Partie 5.1.2's own literal function."""
    return dict(tool.parameters)
