"""Partie 5.4.8 -- Code workflow block. A real, closed-whitelist ast
evaluator, NEVER exec()/eval() on the real, live Python interpreter --
see api/services/workflow_block_code.py's own top docstring for why
that literal spec's own "restricted exec()/eval()" is a real,
well-documented, broken security pattern, not implemented here."""

import pytest

from api.services.workflow_block_code import (
    execute_code_block, format_code_result, sanitize_code, validate_code,
)
from api.services.workflow_blocks import WorkflowBlockError


# --------------------------------------- validate_code / sanitize_code --


def test_validate_code_accepts_real_valid_python():
    """Validation criterion: la validation fonctionne."""
    validate_code("1 + 1", "python")


def test_validate_code_rejects_javascript_honestly():
    """Validation criterion: robustesse -- langage non supporté honnêtement rejeté, pas simulé."""
    with pytest.raises(WorkflowBlockError, match="Unsupported language"):
        validate_code("1 + 1", "javascript")


def test_validate_code_rejects_empty_code():
    with pytest.raises(WorkflowBlockError, match="non-empty"):
        validate_code("", "python")


def test_validate_code_rejects_invalid_syntax():
    with pytest.raises(WorkflowBlockError, match="Invalid code syntax"):
        validate_code("1 +", "python")


def test_sanitize_code_strips_whitespace():
    assert sanitize_code("  1 + 1  \n") == "1 + 1"


# --------------------------------------- execute_code_block: real, safe execution --


def test_execute_code_block_evaluates_arithmetic():
    """Validation criterion: l'exécution du code fonctionne."""
    result = execute_code_block({"code": "a + b", "input_variables": {"a": 2, "b": 3}}, {})
    assert result["output"] == {"result": 5}


def test_execute_code_block_uses_real_context_variables():
    result = execute_code_block({"code": "input.upper()"}, {"input": "hello"})
    assert result["output"] == {"result": "HELLO"}


def test_execute_code_block_supports_safe_string_methods():
    result = execute_code_block({"code": "name.strip().title()"}, {"name": "  ada lovelace  "})
    assert result["output"]["result"] == "Ada Lovelace"


def test_execute_code_block_supports_list_and_dict_literals():
    result = execute_code_block({"code": "len([1, 2, 3])"}, {})
    assert result["output"]["result"] == 3


def test_execute_code_block_respects_output_key():
    result = execute_code_block({"code": "1 + 1", "output_key": "sum"}, {})
    assert result == {"sum": {"result": 2}}


# --------------------------------------- security restrictions --


def test_execute_code_block_rejects_no_real_code_execution_via_dunder():
    """Validation criterion: les restrictions de sécurité sont respectées (pas de fichier/réseau/import)."""
    with pytest.raises(WorkflowBlockError):
        execute_code_block({"code": "(1).__class__"}, {})


def test_execute_code_block_rejects_import():
    with pytest.raises(WorkflowBlockError):
        execute_code_block({"code": "__import__('os')"}, {})


def test_execute_code_block_rejects_arbitrary_builtin_calls():
    with pytest.raises(WorkflowBlockError):
        execute_code_block({"code": "open('/etc/passwd')"}, {})


def test_execute_code_block_rejects_an_unknown_variable():
    with pytest.raises(WorkflowBlockError):
        execute_code_block({"code": "missing + 1"}, {})


def test_execute_code_block_rejects_an_unwhitelisted_method():
    with pytest.raises(WorkflowBlockError):
        execute_code_block({"code": "text.__reduce__()"}, {"text": "hi"})


# --------------------------------------- error handling --


def test_execute_code_block_raises_on_invalid_config():
    """Validation criterion: robustesse -- les erreurs sont gérées."""
    with pytest.raises(WorkflowBlockError):
        execute_code_block({}, {})


def test_format_code_result_wraps_the_real_value():
    assert format_code_result(42) == {"result": 42}
