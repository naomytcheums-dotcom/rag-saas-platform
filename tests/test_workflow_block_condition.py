"""Partie 5.4.7 -- Condition workflow block. Real AST-based safe
evaluation, no eval()/exec(), no JSONLogic dependency."""

import pytest

from api.services.workflow_block_condition import (
    evaluate_condition, execute_condition_block, format_condition_result, validate_condition_config,
)
from api.services.workflow_blocks import WorkflowBlockError


# --------------------------------------- evaluate_condition: comparison/logical/presence/math --


@pytest.mark.parametrize("expr,expected", [
    ("a == 5", True), ("a != 5", False), ("a > 3", True), ("a < 3", False), ("a >= 5", True), ("a <= 4", False),
])
def test_evaluate_condition_comparison_operators(expr, expected):
    """Validation criterion: l'évaluation des conditions fonctionne (comparaison)."""
    assert evaluate_condition(expr, {"a": 5}) is expected


@pytest.mark.parametrize("expr,expected", [
    ("a and b", False), ("a or b", True), ("not a", False),
])
def test_evaluate_condition_logical_operators(expr, expected):
    """Validation criterion: opérateurs logiques."""
    assert evaluate_condition(expr, {"a": True, "b": False}) is expected


def test_evaluate_condition_in_operator():
    """Validation criterion: opérateurs de présence."""
    assert evaluate_condition("a in [1, 2, 3]", {"a": 2}) is True
    assert evaluate_condition("a in [1, 2, 3]", {"a": 9}) is False


def test_evaluate_condition_contains_function():
    assert evaluate_condition("contains(items, x)", {"items": ["a", "b"], "x": "a"}) is True


def test_evaluate_condition_is_empty_function():
    assert evaluate_condition("is_empty(items)", {"items": []}) is True
    assert evaluate_condition("is_empty(items)", {"items": ["a"]}) is False


@pytest.mark.parametrize("expr,expected", [
    ("a + b == 8", True), ("a - b == 2", True), ("a * b == 15", True), ("a % b == 2", True),
])
def test_evaluate_condition_math_operators(expr, expected):
    """Validation criterion: opérateurs mathématiques."""
    assert evaluate_condition(expr, {"a": 5, "b": 3}) is expected


# --------------------------------------- robustness / security --


def test_evaluate_condition_rejects_invalid_syntax():
    """Validation criterion: robustesse -- que se passe-t-il si une condition est invalide."""
    with pytest.raises(WorkflowBlockError, match="Invalid condition syntax"):
        evaluate_condition("a ===", {"a": 1})


def test_evaluate_condition_rejects_an_unknown_variable():
    with pytest.raises(WorkflowBlockError, match="Unknown variable"):
        evaluate_condition("missing == 1", {})


def test_evaluate_condition_rejects_no_real_code_execution():
    """Validation criterion: sécurité -- pas d'injection, pas d'eval()."""
    with pytest.raises(WorkflowBlockError):
        evaluate_condition("__import__('os').system('echo hacked')", {})


def test_evaluate_condition_rejects_arbitrary_function_calls():
    with pytest.raises(WorkflowBlockError):
        evaluate_condition("len(items)", {"items": [1, 2]})


def test_evaluate_condition_rejects_attribute_access():
    with pytest.raises(WorkflowBlockError):
        evaluate_condition("a.__class__", {"a": 1})


# --------------------------------------- validate_condition_config / format_condition_result --


def test_validate_condition_config_rejects_a_missing_condition():
    """Validation criterion: la validation fonctionne."""
    with pytest.raises(WorkflowBlockError, match="condition"):
        validate_condition_config({})


def test_format_condition_result_picks_the_real_branch():
    assert format_condition_result(True, "node_a", "node_b") == {"result": True, "branch": "node_a"}
    assert format_condition_result(False, "node_a", "node_b") == {"result": False, "branch": "node_b"}


# --------------------------------------- execute_condition_block --


def test_execute_condition_block_returns_the_real_branch_taken():
    """Validation criterion: les branches sont correctement exécutées."""
    result = execute_condition_block(
        {"condition": "score >= 50", "true_branch": "pass_node", "false_branch": "fail_node"}, {"score": 75},
    )
    assert result["output"] == {"result": True, "branch": "pass_node"}


def test_execute_condition_block_raises_on_invalid_config():
    with pytest.raises(WorkflowBlockError):
        execute_condition_block({}, {})
