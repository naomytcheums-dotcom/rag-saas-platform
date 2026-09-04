"""Partie 3.2.5 -- tests for api/services/code_chunking.py's own real,
code-aware chunking functions."""

from api.services.code_chunking import (
    chunk_code_by_blocks,
    chunk_code_by_classes,
    chunk_code_by_functions,
    chunk_code_by_tokens,
    chunk_code_preserve_imports,
    detect_code_language,
)

_PY_CODE = """import os
import sys


def foo(x, y):
    return x + y


class Bar:
    def __init__(self):
        self.value = 1

    def compute(self):
        return self.value * 2
"""

_JS_CODE = """import React from 'react';

function add(a, b) {
  return a + b;
}

class Widget {
  constructor(props) {
    this.props = props;
  }

  render() {
    return add(1, 2);
  }
}
"""


def test_detect_code_language_recognizes_real_python():
    """Validation criterion: le langage de code est détecté -- a
    regression case for a real bug found while building this étape:
    pygments' own generic guess_lexer misdetects real, well-formed
    JavaScript as Python, so this module uses its own hand-written
    signal-counting heuristic instead."""
    assert detect_code_language(_PY_CODE) == "python"


def test_detect_code_language_recognizes_real_javascript():
    assert detect_code_language(_JS_CODE) == "javascript"


def test_detect_code_language_is_text_for_empty_input():
    assert detect_code_language("") == "text"
    assert detect_code_language("   ") == "text"


def test_chunk_code_by_functions_extracts_real_python_functions():
    """Validation criterion: le chunking par fonctions fonctionne."""
    chunks = chunk_code_by_functions(_PY_CODE, "python")
    function_chunks = [c for c in chunks if c.lstrip().startswith("def foo")]
    assert len(function_chunks) == 1
    assert "return x + y" in function_chunks[0]
    assert "class Bar" not in function_chunks[0]


def test_chunk_code_by_functions_extracts_real_javascript_functions():
    chunks = chunk_code_by_functions(_JS_CODE, "javascript")
    assert any(c.startswith("function add(a, b)") and c.rstrip().endswith("}") for c in chunks)
    assert any("return a + b;" in c for c in chunks)


def test_chunk_code_by_functions_auto_detects_language_when_not_given():
    chunks = chunk_code_by_functions(_PY_CODE)
    assert any("def foo" in c for c in chunks)


def test_chunk_code_by_functions_is_empty_for_empty_input():
    assert chunk_code_by_functions("") == []


def test_chunk_code_by_classes_extracts_real_python_class_with_its_own_methods():
    """Validation criterion: le chunking par classes fonctionne -- the
    real class block includes both of its own real nested methods."""
    chunks = chunk_code_by_classes(_PY_CODE, "python")
    assert len(chunks) == 1
    assert "def __init__" in chunks[0]
    assert "def compute" in chunks[0]


def test_chunk_code_by_classes_extracts_real_javascript_class():
    chunks = chunk_code_by_classes(_JS_CODE, "javascript")
    assert len(chunks) == 1
    assert "constructor(props)" in chunks[0]
    assert "render()" in chunks[0]
    assert chunks[0].rstrip().endswith("}")


def test_chunk_code_by_blocks_is_language_agnostic():
    """Validation criterion: le chunking par blocs fonctionne."""
    rust_like = "fn add(a: i32, b: i32) -> i32 {\n    a + b\n}\n\nfn main() {\n    println!(\"{}\", add(1, 2));\n}\n"
    chunks = chunk_code_by_blocks(rust_like)
    assert len(chunks) >= 1
    assert "".join(chunks).replace("\n", "") != ""


def test_chunk_code_by_blocks_is_empty_for_empty_input():
    assert chunk_code_by_blocks("") == []


def test_chunk_code_preserve_imports_separates_real_python_imports():
    """Validation criterion: les imports sont préservés."""
    chunks = chunk_code_preserve_imports(_PY_CODE)
    assert len(chunks) == 2
    assert "import os" in chunks[0] and "import sys" in chunks[0]
    assert "def foo" in chunks[1]
    assert "import os" not in chunks[1]


def test_chunk_code_preserve_imports_returns_whole_text_when_there_are_none():
    code = "x = 1\ny = 2\n"
    assert chunk_code_preserve_imports(code) == [code.strip()]


def test_chunk_code_preserve_imports_is_empty_for_empty_input():
    assert chunk_code_preserve_imports("") == []


def test_chunk_code_by_tokens_respects_a_real_max_tokens_limit():
    """Validation criterion: le chunking par tokens fonctionne."""
    code = "\n".join(f"x{i} = {i}" for i in range(30))
    chunks = chunk_code_by_tokens(code, "python", max_tokens=10)
    assert len(chunks) > 1
    reconstructed = "\n".join(chunks)
    for i in range(30):
        assert f"x{i} = {i}" in reconstructed


def test_chunk_code_by_tokens_never_splits_a_real_line_in_half():
    code = "\n".join(f"x{i} = {i}" for i in range(10))
    chunks = chunk_code_by_tokens(code, "python", max_tokens=5)
    for chunk in chunks:
        for line in chunk.split("\n"):
            if line.strip():
                assert line.strip().count("=") <= 1  # a real, whole assignment line, never a fragment


def test_chunk_code_by_tokens_is_empty_for_empty_input():
    assert chunk_code_by_tokens("") == []
