"""Partie 5.2.5 -- extended calculator tool. Pure functions, no
mocking, no DB."""

import pytest

from api.tools.calculator import (
    ADVANCED_CALCULATOR_TOOL, CalculatorError, calculate, format_calculation_result, get_calculation_history,
    get_math_functions, validate_expression,
)


# --------------------------------------- calculate: basic ops --


def test_calculate_basic_arithmetic():
    """Validation criterion: les calculs de base fonctionnent."""
    assert calculate("2 + 3 * 4") == 14
    assert calculate("(2 + 3) ** 2") == 25
    assert calculate("10 % 3") == 1


# --------------------------------------- calculate: functions/constants --


def test_calculate_real_math_functions():
    """Validation criterion: les fonctions mathématiques fonctionnent."""
    assert calculate("sqrt(16)") == 4.0
    assert round(calculate("sin(0)"), 5) == 0.0
    assert calculate("abs(-5)") == 5
    assert calculate("ceil(1.1)") == 2
    assert calculate("floor(1.9)") == 1
    assert calculate("round(1.456, 2)") == 1.46


def test_calculate_real_constants():
    assert round(calculate("pi"), 5) == round(3.14159, 5)
    assert calculate("e") > 2.7


def test_calculate_real_variables():
    """Validation criterion: les calculs avec paramètres fonctionnent."""
    assert calculate("x + y", x=2, y=3) == 5
    assert calculate("x ** 2", x=4) == 16


def test_calculate_unknown_variable_raises():
    with pytest.raises(CalculatorError, match="Unknown variable"):
        calculate("z + 1")


# --------------------------------------- calculate: safety --


def test_calculate_rejects_a_real_code_injection_attempt():
    """Validation criterion: sécurité -- pas d'injection de code."""
    with pytest.raises(CalculatorError):
        calculate("__import__('os').system('echo pwned')")


def test_calculate_rejects_an_unsupported_function():
    """Rejected by validate_expression's own structural check before
    ever reaching real evaluation."""
    with pytest.raises(CalculatorError, match="Invalid or unsafe expression"):
        calculate("open('x')")


def test_calculate_rejects_division_by_zero():
    with pytest.raises(CalculatorError, match="zero"):
        calculate("1 / 0")


def test_calculate_rejects_an_expression_beyond_the_real_max_length():
    with pytest.raises(CalculatorError):
        calculate("1+" * 1000 + "1")


# --------------------------------------- validate_expression --


def test_validate_expression_accepts_a_real_symbolic_expression():
    """Validation criterion: la précision/la validité sont vérifiées
    avant évaluation."""
    assert validate_expression("sqrt(x) + y * pi") is True


def test_validate_expression_rejects_an_unsafe_expression():
    assert validate_expression("__import__('os')") is False


def test_validate_expression_rejects_invalid_syntax():
    assert validate_expression("2 +") is False


# --------------------------------------- get_math_functions / format --


def test_get_math_functions_lists_real_supported_functions():
    functions = get_math_functions()
    assert "sqrt" in functions and "ceil" in functions


def test_format_calculation_result_strips_trailing_zeros():
    assert format_calculation_result(4.0) == "4"
    assert format_calculation_result(1.5) == "1.5"


# --------------------------------------- history --


def test_get_calculation_history_records_real_calculations():
    calculate("1 + 1")
    history = get_calculation_history()
    assert any(h["expression"] == "1 + 1" for h in history)


# --------------------------------------- tool wiring --


async def test_advanced_calculator_tool_handler_works():
    result = await ADVANCED_CALCULATOR_TOOL.handler(expression="sqrt(x)", x=9)
    assert result == "3"
