"""Partie 3.1.4 -- tests for api/services/table_transformation.py."""

import pandas as pd

from api.services.table_transformation import detect_table_headers, normalize_table, table_to_json, table_to_markdown, table_to_text


def _real_table() -> pd.DataFrame:
    return pd.DataFrame({"Name": ["Alice", "Bob"], "Age": [30, 25]})


# --------------------------------------------------------------- table_to_markdown --

def test_table_to_markdown_renders_a_real_pipe_table():
    """Validation criterion: la conversion en Markdown fonctionne."""
    result = table_to_markdown(_real_table())
    lines = result.splitlines()
    assert lines[0] == "| Name | Age |"
    assert lines[1] == "| --- | --- |"
    assert lines[2] == "| Alice | 30 |"
    assert lines[3] == "| Bob | 25 |"


def test_table_to_markdown_handles_an_empty_real_table():
    assert table_to_markdown(pd.DataFrame()) == ""


def test_table_to_markdown_renders_a_missing_real_value_as_blank():
    table = pd.DataFrame({"A": [1, None]})
    result = table_to_markdown(table)
    last_row_cell = result.splitlines()[-1].strip("|").strip()
    assert last_row_cell == ""


# ------------------------------------------------------------------- table_to_json --

def test_table_to_json_returns_one_real_dict_per_row():
    assert table_to_json(_real_table()) == [{"Name": "Alice", "Age": 30}, {"Name": "Bob", "Age": 25}]


def test_table_to_json_converts_a_real_missing_value_to_none():
    table = pd.DataFrame({"A": [1, None]})
    assert table_to_json(table) == [{"A": 1.0}, {"A": None}]


# ------------------------------------------------------------------- table_to_text --

def test_table_to_text_renders_a_real_readable_string():
    result = table_to_text(_real_table())
    assert "Alice" in result
    assert "30" in result


def test_table_to_text_handles_an_empty_real_table():
    assert table_to_text(pd.DataFrame()) == ""


# --------------------------------------------------------------- detect_table_headers --

def test_detect_table_headers_returns_the_real_column_names():
    """Validation criterion (item 3): les en-têtes sont détectés."""
    assert detect_table_headers(_real_table()) == ["Name", "Age"]


def test_detect_table_headers_returns_none_for_a_real_headerless_table():
    """A table built without a real header row (pandas' own default
    RangeIndex columns) has no real headers to detect."""
    table = pd.DataFrame([[1, 2], [3, 4]])
    assert detect_table_headers(table) is None


# ------------------------------------------------------------------- normalize_table --

def test_normalize_table_strips_real_whitespace_from_cells():
    """Validation criterion: la normalisation des tableaux fonctionne."""
    table = pd.DataFrame({"Name": ["  Alice ", "Bob  "]})
    result = normalize_table(table)
    assert result["Name"].tolist() == ["Alice", "Bob"]


def test_normalize_table_drops_a_real_fully_empty_row():
    table = pd.DataFrame({"A": ["x", "", None], "B": ["y", "", None]})
    result = normalize_table(table)
    assert len(result) == 1
    assert result.iloc[0]["A"] == "x"


def test_normalize_table_never_drops_a_real_column():
    table = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    result = normalize_table(table)
    assert list(result.columns) == ["A", "B"]
