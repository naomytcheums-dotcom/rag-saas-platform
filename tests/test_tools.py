"""Tests for api/services/tools.py -- the real, minimal Tool
abstraction Partie 5.1.2-5.1.9 build on. No mocking: every tool handler
here is real, pure Python."""

import pytest

from api.services.tools import (
    CALCULATOR_TOOL, WORD_COUNT_TOOL, ToolSpec, get_tool, get_tool_description,
    get_tool_parameters, list_tools, register_tool,
)


async def test_calculator_evaluates_a_real_expression():
    assert await CALCULATOR_TOOL.handler(expression="2 + 3 * 4") == "14"


async def test_calculator_supports_parentheses_and_power():
    assert await CALCULATOR_TOOL.handler(expression="(2 + 3) ** 2") == "25"


async def test_calculator_rejects_a_real_code_injection_attempt():
    """Validation criterion: this must be a real, safe evaluator -- not
    Python's own eval(), which would execute arbitrary code."""
    with pytest.raises(ValueError):
        await CALCULATOR_TOOL.handler(expression="__import__('os').system('echo pwned')")


async def test_calculator_rejects_division_by_zero():
    with pytest.raises(ValueError):
        await CALCULATOR_TOOL.handler(expression="1 / 0")


async def test_word_count_counts_real_words():
    assert await WORD_COUNT_TOOL.handler(text="the quick brown fox") == "4"


def test_list_tools_includes_the_real_builtins():
    names = {t.name for t in list_tools()}
    assert {"calculator", "word_count"} <= names


def test_get_tool_returns_none_for_an_unknown_name():
    assert get_tool("never-registered") is None


def test_register_tool_adds_a_real_new_tool():
    tool = ToolSpec(
        name="test-only-tool", description="A test tool", parameters={},
        capability_tags=("testing",), handler=WORD_COUNT_TOOL.handler,
    )
    register_tool(tool)
    assert get_tool("test-only-tool") is tool


def test_get_tool_description_and_parameters():
    assert get_tool_description(CALCULATOR_TOOL) == CALCULATOR_TOOL.description
    assert get_tool_parameters(CALCULATOR_TOOL) == {"expression": {"type": "string", "description": "The arithmetic expression to evaluate"}}
