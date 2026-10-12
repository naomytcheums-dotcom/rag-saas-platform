"""Partie 5.4.8 -- security review of the code workflow block (audit item 5.4.8, HIGH).

The block evaluates a single expression with a closed whitelist, never exec()/eval(). The review found three ways round that whitelist,
each reproduced before the fix:
  * `"{0.__class__.__mro__}".format("x")` reads `__dunder__` attributes through the format string;
  * `"x" * 100000000` and `("a" * 10**6).replace("a", "b" * 1000)` allocate 100 MB and 1 GB with no limit;
  * a deeply nested expression raised MemoryError / RecursionError, and `1 / 0` raised ZeroDivisionError, none of which the workflow
    engine handles (it only catches WorkflowBlockError)."""

import pytest

from api.services.workflow_block_code import MAX_CODE_LENGTH, MAX_RESULT_SIZE, execute_code_block
from api.services.workflow_blocks import WorkflowBlockError


def run(code, **variables):
    return execute_code_block({"code": code, "input_variables": variables}, {})["output"]["result"]


# --------------------------------------- format strings --


@pytest.mark.parametrize(
    "code",
    [
        '"{0.__class__.__mro__}".format("x")',
        '"{0.__class__}".format(1)',
        '"{0[secret]}".format(d)',
        '"{0:{1.__class__}}".format("x", "y")',
        '"{a.b}".format("x")',
    ],
)
def test_format_string_cannot_read_attributes_or_items(code):
    with pytest.raises(WorkflowBlockError):
        run(code, d={"secret": "S3CRET"})


def test_plain_format_fields_still_work():
    assert run('"{} and {}".format(a, b)', a="x", b="y") == "x and y"
    assert run('"{0}-{0}".format(a)', a="z") == "z-z"
    assert run('"literal {{braces}}".format()') == "literal {braces}"


# --------------------------------------- memory limits --


@pytest.mark.parametrize("code", ['"x" * 100000000', '100000000 * "x"', "[0] * 100000000", "(1, 2) * 100000000", '"x" * 10 * 10000000'])
def test_repeating_a_sequence_is_bounded(code):
    with pytest.raises(WorkflowBlockError):
        run(code)


def test_repeating_below_the_limit_still_works():
    assert run('"ab" * 3') == "ababab"
    assert len(run('"x" * 1000')) == 1000
    assert run('"x" * 0') == ""
    assert run("2 * 3") == 6


def test_replace_cannot_amplify_a_value_past_the_limit():
    # 1000 characters replaced by 2000 characters each would build 2 million characters.
    with pytest.raises(WorkflowBlockError):
        run('("a" * 1000).replace("a", "b" * 2000)')
    assert run('("a" * 10).replace("a", "bc")') == "bc" * 10


def test_join_cannot_amplify_a_value_past_the_limit():
    with pytest.raises(WorkflowBlockError):
        run('",".join([("x" * 1000)] * 2000)')
    assert run('",".join(["a", "b", "c"])') == "a,b,c"


def test_format_cannot_repeat_a_large_argument_into_many_fields():
    with pytest.raises(WorkflowBlockError):
        run('("{}" * 500).format("x" * 5000)')


def test_a_large_value_from_the_context_cannot_be_amplified():
    big = "a" * (MAX_RESULT_SIZE // 2)
    with pytest.raises(WorkflowBlockError):
        run("value + value + value", value=big)


# --------------------------------------- parser and runtime failures --


def test_code_longer_than_the_limit_is_rejected():
    with pytest.raises(WorkflowBlockError, match="longer than"):
        run("1" + "+1" * MAX_CODE_LENGTH)


@pytest.mark.parametrize("code", ["-" * 4000 + "1", "1+" * 2400 + "1", "[1]" + "[0]" * 1600, "not " * 1200 + "1"])
def test_deeply_nested_code_fails_as_a_block_error_not_a_crash(code):
    assert len(code) <= MAX_CODE_LENGTH
    try:
        run(code)
    except WorkflowBlockError:
        pass  # rejected cleanly; any other exception type propagates and fails the test


@pytest.mark.parametrize("code", ["1 / 0", "1 % 0", '"a" + 1', "d['missing']", "[1][5]", "int('abc')"])
def test_runtime_errors_of_the_expression_are_block_errors(code):
    with pytest.raises(WorkflowBlockError) as info:
        run(code, d={})
    assert "failed" in str(info.value)


def test_runtime_error_message_does_not_echo_the_values():
    with pytest.raises(WorkflowBlockError) as info:
        run("int(secret)", secret="TOP-SECRET-VALUE")
    assert "TOP-SECRET-VALUE" not in str(info.value)


def test_a_nul_byte_in_the_code_is_a_block_error():
    with pytest.raises(WorkflowBlockError):
        run("1 +\x00 1")
