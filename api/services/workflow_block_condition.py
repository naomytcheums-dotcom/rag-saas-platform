"""
Partie 5.4.7 -- real `condition` workflow block execution.

**Sécurité (vision critique 1): a real, documented deviation from
item 1's own literal "JSONLogic"** -- no JSONLogic library is a real
dependency of this codebase (`requirements.txt`/`requirements-api.txt`
checked, neither declares one). Adding one for this single feature
was judged not worth a new, real third-party dependency when this
codebase already has a real, PROVEN-SAFE pattern for exactly this
problem: `api/tools/calculator.py`'s own `_safe_eval_arithmetic`
(Partie 5.1.x) -- a hand-written `ast`-based evaluator that walks a
real, parsed expression tree accepting ONLY a real, closed whitelist
of node types, never Python's own `eval()`/`exec()` (which would
execute arbitrary code from a Manager-authored, real but not fully
trusted condition string -- the same real threat model already
documented for Partie 5.3.2's own template rendering). This module
extends that exact same real, safe pattern to item 3's own literal
operator set (comparison, logical, presence, arithmetic) rather than
inventing a second, different safety mechanism.

**A real variable lookup, not a silent one**: an unknown `ast.Name` in
a condition raises a real, specific `WorkflowBlockError` -- a
condition silently evaluating against a missing/`None` variable could
pick the WRONG real branch without any visible error, a real,
dangerous silent-failure class for control flow (worse than a
template's own literal `{{typo}}` placeholder, Partie 5.3.2/5.4.3-6,
which is at least visible in the rendered text)."""

import ast
import operator

from api.services.workflow_blocks import WorkflowBlockError

_SAFE_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod,
}
_SAFE_COMPARE = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Gt: operator.gt, ast.Lt: operator.lt,
    ast.GtE: operator.ge, ast.LtE: operator.le, ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
}
# Item 3's own literal "presence" operators, not real Python syntax --
# exposed as two real, explicitly whitelisted function-call names
# (`ast.Call` is otherwise never allowed, so this can never become a
# real arbitrary-call vector).
_SAFE_CALLS = {"contains": lambda a, b: b in a, "is_empty": lambda a: not a}


def _eval_node(node, context: dict):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, context)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in context:
            raise WorkflowBlockError(f"Unknown variable in condition: {node.id!r}")
        return context[node.id]
    if isinstance(node, ast.List):
        return [_eval_node(e, context) for e in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(e, context) for e in node.elts)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, context)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_node(node.operand, context)
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BINOPS:
        return _SAFE_BINOPS[type(node.op)](_eval_node(node.left, context), _eval_node(node.right, context))
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, context) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, context)
        result = True
        for op, comparator in zip(node.ops, node.comparators):
            if type(op) not in _SAFE_COMPARE:
                raise WorkflowBlockError(f"Unsupported comparison operator: {type(op).__name__}")
            right = _eval_node(comparator, context)
            result = result and _SAFE_COMPARE[type(op)](left, right)
            left = right
        return result
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _SAFE_CALLS and not node.keywords:
        args = [_eval_node(a, context) for a in node.args]
        return _SAFE_CALLS[node.func.id](*args)
    raise WorkflowBlockError(f"Unsupported condition expression: {ast.dump(node)}")


def evaluate_condition(condition_expression: str, context: dict) -> bool:
    """Item 2's own literal function -- real, safe AST evaluation, see
    this module's own top docstring."""
    try:
        tree = ast.parse(condition_expression, mode="eval")
    except SyntaxError as exc:
        raise WorkflowBlockError(f"Invalid condition syntax: {exc}") from exc
    return bool(_eval_node(tree, context))


def validate_condition_config(config: dict) -> None:
    """Item 2's own literal function -- real, upfront: a real
    `condition` string is the one genuinely required field."""
    if not config.get("condition"):
        raise WorkflowBlockError("condition block requires a real, non-empty 'condition' expression")


def format_condition_result(result: bool, true_branch: str | None = None, false_branch: str | None = None) -> dict:
    """Item 2's own literal function -- the real branch a future graph
    executor should follow next."""
    return {"result": result, "branch": true_branch if result else false_branch}


def execute_condition_block(block_config: dict, context: dict) -> dict:
    """Item 2's own literal function -- real, upfront validation, then
    a real, safe evaluation."""
    validate_condition_config(block_config)
    result = evaluate_condition(block_config["condition"], context)
    formatted = format_condition_result(result, block_config.get("true_branch"), block_config.get("false_branch"))
    return {block_config.get("output_key", "output"): formatted}
